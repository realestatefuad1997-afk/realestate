from flask import Blueprint, render_template, abort, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from flask_babel import gettext as _
from ..extensions import db
from ..models import Property, Contract, MaintenanceRequest, Complaint
from werkzeug.utils import secure_filename
import os
import smtplib
from email.message import EmailMessage


employee_bp = Blueprint("employee", __name__)


def employee_required(func):
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not (current_user.is_employee or current_user.is_admin):
            return abort(403)
        return func(*args, **kwargs)

    return wrapper


@employee_bp.route("/")
@login_required
@employee_required
def dashboard():
    properties = Property.query.order_by(Property.created_at.desc()).limit(10).all()
    contracts = Contract.query.order_by(Contract.created_at.desc()).limit(10).all()
    maints = MaintenanceRequest.query.order_by(MaintenanceRequest.created_at.desc()).limit(10).all()
    complaints = Complaint.query.order_by(Complaint.created_at.desc()).limit(10).all()
    return render_template(
        "employee/dashboard.html",
        properties=properties,
        contracts=contracts,
        maintenance_requests=maints,
        complaints=complaints,
    )


def _send_email(recipient: str, subject: str, body: str) -> bool:
    """Send a simple email using SMTP settings if configured.

    Returns True if attempt was made and did not raise, False otherwise.
    """
    mail_server = current_app.config.get("MAIL_SERVER")
    if not mail_server or not recipient:
        return False
    mail_port = int(current_app.config.get("MAIL_PORT", 587))
    use_tls = bool(current_app.config.get("MAIL_USE_TLS", True))
    use_ssl = bool(current_app.config.get("MAIL_USE_SSL", False))
    username = current_app.config.get("MAIL_USERNAME")
    password = current_app.config.get("MAIL_PASSWORD")
    sender = current_app.config.get("MAIL_DEFAULT_SENDER") or username or "no-reply@example.com"

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        if use_ssl:
            with smtplib.SMTP_SSL(mail_server, mail_port) as server:
                if username and password:
                    server.login(username, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(mail_server, mail_port) as server:
                server.ehlo()
                if use_tls:
                    server.starttls()
                if username and password:
                    server.login(username, password)
                server.send_message(msg)
        return True
    except Exception:
        return False


@employee_bp.route("/maintenance/<int:req_id>", methods=["GET", "POST"])
@login_required
@employee_required
def maintenance_detail(req_id: int):
    req = MaintenanceRequest.query.get_or_404(req_id)
    if request.method == "POST":
        new_status = request.form.get("status") or req.status
        response = request.form.get("response")
        req.status = new_status
        req.response = response
        db.session.commit()
        flash(_("Maintenance request updated"), "success")
        if request.form.get("notify_client"):
            from ..models import User
            tenant = User.query.get(req.tenant_id) if req.tenant_id else None
            if tenant and tenant.email:
                subject = _("Maintenance Request #%(num)s Update", num=req.id)
                body = (
                    _("Title")
                    + f": {req.title}\n"
                    + _("Status")
                    + f": {req.status}\n\n"
                )
                if req.response:
                    body += _("Notes") + f":\n{req.response}\n"
                sent = _send_email(tenant.email, subject, body)
                if sent:
                    flash(_("Notification sent to client"), "info")
                else:
                    flash(_("Notification not sent (mail not configured)"), "warning")
        return redirect(url_for("employee.maintenance_detail", req_id=req.id))
    # Load related data
    tenant = None
    prop = None
    if req.tenant_id:
        from ..models import User
        tenant = User.query.get(req.tenant_id)
    if req.property_id:
        prop = Property.query.get(req.property_id)
    return render_template("employee/maintenance_detail.html", req=req, tenant=tenant, property=prop)


@employee_bp.route("/complaints/<int:comp_id>", methods=["GET", "POST"])
@login_required
@employee_required
def complaint_detail(comp_id: int):
    comp = Complaint.query.get_or_404(comp_id)
    if request.method == "POST":
        new_status = request.form.get("status") or comp.status
        response = request.form.get("response")
        comp.status = new_status
        comp.response = response
        db.session.commit()
        flash(_("Complaint updated"), "success")
        if request.form.get("notify_client"):
            from ..models import User
            tenant = User.query.get(comp.tenant_id) if comp.tenant_id else None
            if tenant and tenant.email:
                subject = _("Complaint #%(num)s Update", num=comp.id)
                body = (
                    _("Subject")
                    + f": {comp.subject}\n"
                    + _("Status")
                    + f": {comp.status}\n\n"
                )
                if comp.response:
                    body += _("Notes") + f":\n{comp.response}\n"
                sent = _send_email(tenant.email, subject, body)
                if sent:
                    flash(_("Notification sent to client"), "info")
                else:
                    flash(_("Notification not sent (mail not configured)"), "warning")
        return redirect(url_for("employee.complaint_detail", comp_id=comp.id))
    tenant = None
    if comp.tenant_id:
        from ..models import User
        tenant = User.query.get(comp.tenant_id)
    return render_template("employee/complaint_detail.html", comp=comp, tenant=tenant)


@employee_bp.route("/properties")
@login_required
@employee_required
def properties_list():
    properties = Property.query.order_by(Property.created_at.desc()).all()
    return render_template("employee/properties_list.html", properties=properties)


@employee_bp.route("/properties/create", methods=["GET", "POST"])
@login_required
@employee_required
def properties_create():
    if request.method == "POST":
        title = request.form.get("title")
        price = request.form.get("price")
        description = request.form.get("description")
        images_filenames = []
        images_files = request.files.getlist("images")
        upload_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "properties")
        os.makedirs(upload_dir, exist_ok=True)
        for f in images_files:
            if f and f.filename:
                filename = secure_filename(f.filename)
                path = os.path.join(upload_dir, filename)
                f.save(path)
                images_filenames.append(f"properties/{filename}")
        images_value = ",".join(images_filenames) if images_filenames else None
        prop = Property(title=title, price=price, description=description, status="available", images=images_value)
        db.session.add(prop)
        db.session.commit()
        flash(_("Property created"), "success")
        return redirect(url_for("employee.properties_list"))
    return render_template("employee/property_form.html", property=None)


@employee_bp.route("/properties/<int:prop_id>/edit", methods=["GET", "POST"])
@login_required
@employee_required
def properties_edit(prop_id: int):
    prop = Property.query.get_or_404(prop_id)
    if request.method == "POST":
        prop.title = request.form.get("title")
        prop.price = request.form.get("price")
        prop.description = request.form.get("description")
        prop.status = request.form.get("status") or prop.status
        images_files = request.files.getlist("images")
        if images_files:
            upload_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "properties")
            os.makedirs(upload_dir, exist_ok=True)
            new_files = []
            for f in images_files:
                if f and f.filename:
                    filename = secure_filename(f.filename)
                    path = os.path.join(upload_dir, filename)
                    f.save(path)
                    new_files.append(f"properties/{filename}")
            if new_files:
                existing = prop.images.split(",") if prop.images else []
                prop.images = ",".join(existing + new_files)
        db.session.commit()
        flash(_("Property updated"), "success")
        return redirect(url_for("employee.properties_list"))
    return render_template("employee/property_form.html", property=prop)


@employee_bp.route("/properties/<int:prop_id>/delete", methods=["POST"])
@login_required
@employee_required
def properties_delete(prop_id: int):
    prop = Property.query.get_or_404(prop_id)
    db.session.delete(prop)
    db.session.commit()
    flash(_("Property deleted"), "info")
    return redirect(url_for("employee.properties_list"))


@employee_bp.route("/contracts")
@login_required
@employee_required
def contracts_list():
    contracts = Contract.query.order_by(Contract.created_at.desc()).all()
    return render_template("employee/contracts_list.html", contracts=contracts)


@employee_bp.route("/contracts/create", methods=["GET", "POST"])
@login_required
@employee_required
def contracts_create():
    from ..models import User
    if request.method == "POST":
        property_id = int(request.form.get("property_id"))
        tenant_id = int(request.form.get("tenant_id"))
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")
        rent_amount = request.form.get("rent_amount")
        # Save optional contract document
        doc = request.files.get("document")
        document_path = None
        if doc and doc.filename:
            upload_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "contracts")
            os.makedirs(upload_dir, exist_ok=True)
            filename = secure_filename(doc.filename)
            path = os.path.join(upload_dir, filename)
            doc.save(path)
            document_path = f"contracts/{filename}"

        contract = Contract(
            property_id=property_id,
            tenant_id=tenant_id,
            start_date=start_date,
            end_date=end_date,
            rent_amount=rent_amount,
            status="active",
            document_path=document_path,
        )
        db.session.add(contract)
        db.session.commit()
        flash(_("Contract created"), "success")
        return redirect(url_for("employee.contracts_list"))
    properties = Property.query.all()
    tenants = User.query.filter_by(role="tenant").all()
    return render_template("employee/contract_form.html", properties=properties, tenants=tenants)

