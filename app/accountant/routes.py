from flask import Blueprint, render_template, abort, request, redirect, url_for, flash
from flask_login import login_required, current_user
from flask_babel import gettext as _
from ..extensions import db
from ..models import Payment, Invoice
from flask import current_app, send_file
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from openpyxl import Workbook
import io
import os
from datetime import date
from sqlalchemy import text


accountant_bp = Blueprint("accountant", __name__)


def accountant_required(func):
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not (current_user.is_accountant or current_user.is_admin):
            return abort(403)
        return func(*args, **kwargs)

    return wrapper


@accountant_bp.route("/")
@login_required
@accountant_required
def dashboard():
    payments = Payment.query.order_by(Payment.due_date.asc()).all()
    total_paid = (
        db.session.query(db.func.coalesce(db.func.sum(Payment.amount), 0))
        .filter_by(status="paid")
        .scalar()
    )
    return render_template("accountant/dashboard.html", payments=payments, total_paid=total_paid)


@accountant_bp.route("/payments/<int:payment_id>/mark", methods=["POST"])
@login_required
@accountant_required
def mark_payment(payment_id: int):
    payment = Payment.query.get_or_404(payment_id)
    new_status = request.form.get("status")
    if new_status in {"paid", "unpaid"}:
        payment.status = new_status
        db.session.commit()
        flash(_("Payment status updated"), "success")
    return redirect(url_for("accountant.dashboard"))


@accountant_bp.route("/payments/<int:payment_id>/invoice")
@login_required
@accountant_required
def generate_invoice(payment_id: int):
    payment = Payment.query.get_or_404(payment_id)
    # Create PDF in memory
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, height - 72, "Invoice")
    c.setFont("Helvetica", 12)
    c.drawString(72, height - 110, f"Invoice for Payment ID: {payment.id}")
    c.drawString(72, height - 130, f"Contract ID: {payment.contract_id}")
    c.drawString(72, height - 150, f"Amount: {payment.amount}")
    c.drawString(72, height - 170, f"Due Date: {payment.due_date}")
    c.drawString(72, height - 190, f"Status: {payment.status}")
    c.showPage()
    c.save()
    buffer.seek(0)

    # Save to disk
    invoices_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "invoices")
    os.makedirs(invoices_dir, exist_ok=True)
    file_name = f"invoice_{payment.id}.pdf"
    file_path = os.path.join(invoices_dir, file_name)
    with open(file_path, "wb") as f:
        f.write(buffer.getvalue())

    # Create or update DB record
    if payment.invoice:
        payment.invoice.file_path = f"invoices/{file_name}"
    else:
        inv = Invoice(payment_id=payment.id, file_path=f"invoices/{file_name}")
        db.session.add(inv)
    db.session.commit()

    return redirect(url_for("accountant.dashboard"))


@accountant_bp.route("/invoices/<int:payment_id>/download")
@login_required
@accountant_required
def download_invoice(payment_id: int):
    payment = Payment.query.get_or_404(payment_id)
    if not payment.invoice:
        return abort(404)
    file_path = os.path.join(current_app.config["UPLOAD_FOLDER"], payment.invoice.file_path)
    return send_file(file_path, mimetype="application/pdf", as_attachment=True, download_name=os.path.basename(file_path))


@accountant_bp.route("/export/excel")
@login_required
@accountant_required
def export_payments_excel():
    wb = Workbook()
    ws = wb.active
    ws.title = "Payments"
    ws.append(["ID", "Contract", "Amount", "Due Date", "Paid Date", "Method", "Status"])
    for p in Payment.query.order_by(Payment.due_date.asc()).all():
        ws.append([p.id, p.contract_id, float(p.amount), str(p.due_date), str(p.paid_date or ""), p.method or "", p.status])
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name="payments.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@accountant_bp.route("/export/pdf")
@login_required
@accountant_required
def export_payments_pdf():
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, height - 72, "Payments Report")
    c.setFont("Helvetica", 11)
    y = height - 110
    for p in Payment.query.order_by(Payment.due_date.asc()).all():
        line = f"#{p.id} Contract:{p.contract_id} Due:{p.due_date} Amount:{p.amount} Status:{p.status}"
        c.drawString(72, y, line)
        y -= 18
        if y < 72:
            c.showPage()
            y = height - 72
    c.showPage()
    c.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="payments.pdf", mimetype="application/pdf")


@accountant_bp.route("/overview")
@login_required
@accountant_required
def financial_overview():
    """Comprehensive financial overview: totals and last 12 months breakdown."""
    # --- Totals ---
    total_income = (
        db.session.query(db.func.coalesce(db.func.sum(Payment.amount), 0))
        .filter_by(status="paid")
        .scalar()
        or 0
    )

    # Expenses may be in an optional "expenses" table
    total_expenses = 0
    monthly_expenses: list[float] = []
    expenses_date_column = None
    try:
        inspector = db.inspect(db.engine)
        if inspector.has_table("expenses"):
            # Sum total expenses
            res = db.session.execute(text("SELECT COALESCE(SUM(amount), 0) FROM expenses"))
            total_expenses = res.scalar() or 0
            # Try to detect a usable date column for monthly breakdown
            cols = inspector.get_columns("expenses")
            names = {c.get("name") for c in cols}
            for candidate in ("spent_at", "date", "created_at"):
                if candidate in names:
                    expenses_date_column = candidate
                    break
    except Exception:
        total_expenses = 0
        expenses_date_column = None

    # --- Build last 12 month ranges (ascending) ---
    def add_months(year: int, month: int, delta: int) -> tuple[int, int]:
        total = year * 12 + (month - 1) + delta
        y = total // 12
        m = (total % 12) + 1
        return y, m

    def first_of_month(y: int, m: int) -> date:
        return date(y, m, 1)

    def next_month_start(y: int, m: int) -> date:
        y2, m2 = add_months(y, m, 1)
        return date(y2, m2, 1)

    y0, m0 = date.today().year, date.today().month
    month_ranges: list[tuple[date, date]] = []
    month_labels: list[str] = []
    for k in range(11, -1, -1):
        yk, mk = add_months(y0, m0, -k)
        start = first_of_month(yk, mk)
        end = next_month_start(yk, mk)
        month_ranges.append((start, end))
        month_labels.append(f"{yk:04d}-{mk:02d}")

    # --- Monthly income ---
    monthly_income: list[float] = []
    for start, end in month_ranges:
        total = (
            db.session.query(db.func.coalesce(db.func.sum(Payment.amount), 0))
            .filter(
                Payment.status == "paid",
                db.or_(
                    db.and_(Payment.paid_date != None, Payment.paid_date >= start, Payment.paid_date < end),
                    db.and_(Payment.paid_date == None, Payment.due_date >= start, Payment.due_date < end),
                ),
            )
            .scalar()
            or 0
        )
        try:
            monthly_income.append(float(total))
        except Exception:
            monthly_income.append(0.0)

    # --- Monthly expenses (if table and date column exist) ---
    if expenses_date_column is not None:
        monthly_expenses = []
        for start, end in month_ranges:
            q = text(
                f"SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE {expenses_date_column} >= :start AND {expenses_date_column} < :end"
            )
            try:
                r = db.session.execute(q, {"start": start, "end": end})
                monthly_expenses.append(float(r.scalar() or 0))
            except Exception:
                monthly_expenses.append(0.0)
    else:
        monthly_expenses = [0.0 for _ in month_ranges]

    # --- Profits ---
    try:
        profit_total = float(total_income) - float(total_expenses)
    except Exception:
        profit_total = 0.0

    monthly_profit = [round((monthly_income[i] - monthly_expenses[i]), 2) for i in range(len(month_ranges))]

    return render_template(
        "accountant/financial_overview.html",
        total_income=total_income,
        total_expenses=total_expenses,
        profit_total=profit_total,
        month_labels=month_labels,
        monthly_income=monthly_income,
        monthly_expenses=monthly_expenses,
        monthly_profit=monthly_profit,
    )
