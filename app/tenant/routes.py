from flask import Blueprint, render_template, abort, request, redirect, url_for, flash
from flask_login import login_required, current_user
from flask_babel import gettext as _
from ..extensions import db
from ..models import Contract, Payment, MaintenanceRequest, Complaint


tenant_bp = Blueprint("tenant", __name__)


def tenant_required(func):
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_tenant:
            return abort(403)
        return func(*args, **kwargs)

    return wrapper


@tenant_bp.route("/")
@login_required
@tenant_required
def dashboard():
    contracts = Contract.query.filter_by(tenant_id=current_user.id).all()
    payments = (
        Payment.query.join(Contract, Payment.contract_id == Contract.id)
        .filter(Contract.tenant_id == current_user.id)
        .all()
    )
    return render_template("tenant/dashboard.html", contracts=contracts, payments=payments)


@tenant_bp.route("/contracts/<int:contract_id>")
@login_required
@tenant_required
def contract_detail(contract_id: int):
    contract = Contract.query.get_or_404(contract_id)
    if contract.tenant_id != current_user.id:
        return abort(403)
    return render_template("tenant/contract_detail.html", contract=contract)


@tenant_bp.route("/maintenance")
@login_required
@tenant_required
def maintenance_list():
    items = (
        MaintenanceRequest.query.filter_by(tenant_id=current_user.id)
        .order_by(MaintenanceRequest.created_at.desc())
        .all()
    )
    return render_template("tenant/maintenance_list.html", items=items)


@tenant_bp.route("/maintenance/create", methods=["GET", "POST"])
@login_required
@tenant_required
def maintenance_create():
    contracts = Contract.query.filter_by(tenant_id=current_user.id).all()
    if request.method == "POST":
        subject = (request.form.get("subject") or "").strip()
        description = (request.form.get("description") or "").strip()
        priority = (request.form.get("priority") or "normal").strip()
        contract_id = request.form.get("contract_id")
        selected_contract = None
        if contract_id:
            selected_contract = Contract.query.get(int(contract_id))
            if not selected_contract or selected_contract.tenant_id != current_user.id:
                selected_contract = None
        if not subject or not description:
            flash(_("Please fill in all required fields"), "warning")
            return render_template("tenant/maintenance_form.html", contracts=contracts)
        item = MaintenanceRequest(
            tenant_id=current_user.id,
            contract_id=selected_contract.id if selected_contract else None,
            subject=subject,
            description=description,
            status="open",
            priority=priority if priority in {"low", "normal", "high"} else "normal",
        )
        db.session.add(item)
        db.session.commit()
        flash(_("Maintenance request submitted"), "success")
        return redirect(url_for("tenant.maintenance_list"))
    return render_template("tenant/maintenance_form.html", contracts=contracts)


@tenant_bp.route("/complaints")
@login_required
@tenant_required
def complaints_list():
    items = (
        Complaint.query.filter_by(tenant_id=current_user.id)
        .order_by(Complaint.created_at.desc())
        .all()
    )
    return render_template("tenant/complaints_list.html", items=items)


@tenant_bp.route("/complaints/create", methods=["GET", "POST"])
@login_required
@tenant_required
def complaints_create():
    contracts = Contract.query.filter_by(tenant_id=current_user.id).all()
    if request.method == "POST":
        subject = (request.form.get("subject") or "").strip()
        description = (request.form.get("description") or "").strip()
        contract_id = request.form.get("contract_id")
        selected_contract = None
        if contract_id:
            selected_contract = Contract.query.get(int(contract_id))
            if not selected_contract or selected_contract.tenant_id != current_user.id:
                selected_contract = None
        if not subject or not description:
            flash(_("Please fill in all required fields"), "warning")
            return render_template("tenant/complaint_form.html", contracts=contracts)
        item = Complaint(
            tenant_id=current_user.id,
            contract_id=selected_contract.id if selected_contract else None,
            subject=subject,
            description=description,
            status="open",
        )
        db.session.add(item)
        db.session.commit()
        flash(_("Complaint submitted"), "success")
        return redirect(url_for("tenant.complaints_list"))
    return render_template("tenant/complaint_form.html", contracts=contracts)

