from flask import Blueprint, render_template, abort, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from flask_babel import gettext as _
from ..extensions import db
from ..models import Property, Contract, MaintenanceRequest, Complaint
from werkzeug.utils import secure_filename
import os


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

