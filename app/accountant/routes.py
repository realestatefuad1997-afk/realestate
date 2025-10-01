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

