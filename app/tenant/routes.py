from flask import Blueprint, render_template, abort, request, redirect, url_for, flash
from flask_login import login_required, current_user
from flask_babel import gettext as _
from ..models import Contract, Payment, MaintenanceRequest, Complaint
from ..extensions import db


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
    maints = MaintenanceRequest.query.filter_by(tenant_id=current_user.id).order_by(MaintenanceRequest.created_at.desc()).all()
    complaints = Complaint.query.filter_by(tenant_id=current_user.id).order_by(Complaint.created_at.desc()).all()
    return render_template(
        "tenant/dashboard.html",
        contracts=contracts,
        payments=payments,
        maintenance_requests=maints,
        complaints=complaints,
    )


@tenant_bp.route("/maintenance/create", methods=["GET", "POST"])
@login_required
@tenant_required
def maintenance_create():
    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        property_id = request.form.get("property_id") or None
        m = MaintenanceRequest(
            tenant_id=current_user.id,
            property_id=int(property_id) if property_id else None,
            title=title,
            description=description,
            status="new",
        )
        db.session.add(m)
        db.session.commit()
        flash(_("Maintenance request submitted"), "success")
        return redirect(url_for("tenant.dashboard"))
    # Provide properties from tenant's contracts as convenience
    props = (
        Contract.query.filter_by(tenant_id=current_user.id)
        .join(Contract.property)
        .with_entities(Contract.property)
        .all()
    )
    properties = [p[0] for p in props]
    return render_template("tenant/maintenance_form.html", properties=properties)


@tenant_bp.route("/complaints/create", methods=["GET", "POST"])
@login_required
@tenant_required
def complaint_create():
    if request.method == "POST":
        subject = request.form.get("subject")
        description = request.form.get("description")
        c = Complaint(
            tenant_id=current_user.id,
            subject=subject,
            description=description,
            status="new",
        )
        db.session.add(c)
        db.session.commit()
        flash(_("Complaint submitted"), "success")
        return redirect(url_for("tenant.dashboard"))
    return render_template("tenant/complaint_form.html")


@tenant_bp.route("/maintenance/<int:request_id>")
@login_required
@tenant_required
def maintenance_show(request_id: int):
    m = (
        MaintenanceRequest.query.filter_by(id=request_id, tenant_id=current_user.id)
        .first()
    )
    if not m:
        return abort(404)
    return render_template("tenant/maintenance_show.html", m=m)


@tenant_bp.route("/complaints/<int:complaint_id>")
@login_required
@tenant_required
def complaint_show(complaint_id: int):
    c = Complaint.query.filter_by(id=complaint_id, tenant_id=current_user.id).first()
    if not c:
        return abort(404)
    return render_template("tenant/complaint_show.html", c=c)
