from flask import Blueprint, render_template, abort, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from flask_babel import gettext as _
from ..extensions import db
from ..models import Property, Contract, MaintenanceRequest, Complaint, Apartment
from werkzeug.utils import secure_filename
import os
from itsdangerous import URLSafeSerializer
from uuid import uuid4


# --- Image upload helpers ---
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png"}


def _is_allowed_image(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def _save_uploaded_images(files, subfolder: str):
    """Save uploaded image FileStorage list into UPLOAD_FOLDER/subfolder.

    Returns list of relative paths (e.g., "properties/<name>.jpg").
    """
    saved_relpaths = []
    if not files:
        return saved_relpaths

    upload_root = current_app.config.get("UPLOAD_FOLDER", "uploads")
    upload_dir = os.path.join(upload_root, subfolder)
    os.makedirs(upload_dir, exist_ok=True)

    for f in files:
        if not f or not getattr(f, "filename", None):
            continue
        original = secure_filename(f.filename)
        if not _is_allowed_image(original):
            flash(_(f"Skipping file '{original}': invalid image type. Allowed: jpg, jpeg, png"), "warning")
            continue
        ext = original.rsplit(".", 1)[1].lower()
        unique_name = f"{uuid4().hex}.{ext}"
        abs_path = os.path.join(upload_dir, unique_name)
        f.save(abs_path)
        saved_relpaths.append(f"{subfolder}/{unique_name}")
    return saved_relpaths


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
    only = (request.args.get("only") or "").strip().lower()
    # Separate buildings and standalone apartments
    base_buildings_q = Property.query.filter_by(property_type="building")
    base_apartments_q = Property.query.filter_by(property_type="apartment")

    if only == "unleased":
        # Filter properties that have no active contract covering today
        from datetime import date
        today = date.today()
        active_props_subq = (
            db.session.query(Contract.property_id)
            .filter(
                Contract.status == "active",
                Contract.start_date <= today,
                Contract.end_date >= today,
            )
            .subquery()
        )
        base_buildings_q = base_buildings_q.filter(~Property.id.in_(active_props_subq))
        base_apartments_q = base_apartments_q.filter(~Property.id.in_(active_props_subq))

    buildings = base_buildings_q.order_by(Property.created_at.desc()).all()
    standalone_apartments = base_apartments_q.order_by(Property.created_at.desc()).all()
    serializer = URLSafeSerializer(current_app.config["SECRET_KEY"], salt="property-share")
    share_tokens = {p.id: serializer.dumps(p.id) for p in buildings + standalone_apartments}
    return render_template(
        "employee/properties_list.html",
        buildings=buildings,
        standalone_apartments=standalone_apartments,
        share_tokens=share_tokens,
        only=only,
    )


@employee_bp.route("/properties/create", methods=["GET", "POST"])
@login_required
@employee_required
def properties_create():
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        property_type = (request.form.get("property_type") or "building").strip()

        if not title:
            flash(_("All fields are required"), "danger")
            return redirect(url_for("employee.properties_create"))

        # Prepare base kwargs with only common fields
        prop_kwargs = dict(
            title=title,
            status="available",
            property_type=property_type,
        )

        if property_type == "building":
            # Accept number of apartments and floors, and optional images for buildings
            num_apartments_raw = (request.form.get("num_apartments") or "").strip()
            num_floors_raw = (request.form.get("num_floors") or "").strip()

            # Basic numeric validation
            def parse_non_negative_int(value_str):
                return int(value_str) if value_str.isdigit() and int(value_str) >= 0 else None

            num_apartments = parse_non_negative_int(num_apartments_raw)
            num_floors = parse_non_negative_int(num_floors_raw)
            prop_kwargs.update(num_apartments=num_apartments, num_floors=num_floors)

            # Optional images for buildings
            images_files = request.files.getlist("images")
            building_images = _save_uploaded_images(images_files, "properties")
            if building_images:
                prop_kwargs.update(images=",".join(building_images))
        else:
            # Standalone apartment fields + optional metadata
            price = request.form.get("price")
            description = request.form.get("description")
            apt_number = (request.form.get("number") or "").strip() or None
            floor_raw = (request.form.get("floor") or "").strip()
            area_raw = (request.form.get("area_sqm") or "").strip()
            bedrooms_raw = (request.form.get("bedrooms") or "").strip()
            bathrooms_raw = (request.form.get("bathrooms") or "").strip()
            floor_val = int(floor_raw) if floor_raw.isdigit() else None
            bedrooms_val = int(bedrooms_raw) if bedrooms_raw.isdigit() else None
            bathrooms_val = int(bathrooms_raw) if bathrooms_raw.isdigit() else None
            area_val = area_raw or None

            images_files = request.files.getlist("images")
            apt_images = _save_uploaded_images(images_files, "properties")
            images_value = ",".join(apt_images) if apt_images else None

            prop_kwargs.update(
                price=price,
                description=description,
                images=images_value,
                number=apt_number,
                floor=floor_val,
                area_sqm=area_val,
                bedrooms=bedrooms_val,
                bathrooms=bathrooms_val,
            )
        prop = Property(**prop_kwargs)
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
        # Building fields
        num_apartments_raw = (request.form.get("num_apartments") or "").strip()
        num_floors_raw = (request.form.get("num_floors") or "").strip()
        prop.num_apartments = int(num_apartments_raw) if num_apartments_raw.isdigit() else None
        prop.num_floors = int(num_floors_raw) if num_floors_raw.isdigit() else None
        # Standalone apartment fields
        if prop.property_type == "apartment":
            prop.number = (request.form.get("number") or "").strip() or None
            floor_raw = (request.form.get("floor") or "").strip()
            area_raw = (request.form.get("area_sqm") or "").strip()
            bedrooms_raw = (request.form.get("bedrooms") or "").strip()
            bathrooms_raw = (request.form.get("bathrooms") or "").strip()
            prop.floor = int(floor_raw) if floor_raw.isdigit() else None
            prop.area_sqm = area_raw or None
            prop.bedrooms = int(bedrooms_raw) if bedrooms_raw.isdigit() else None
            prop.bathrooms = int(bathrooms_raw) if bathrooms_raw.isdigit() else None
        images_files = request.files.getlist("images")
        if images_files:
            new_files = _save_uploaded_images(images_files, "properties")
            if new_files:
                existing = prop.images.split(",") if prop.images else []
                prop.images = ",".join(existing + new_files)
        db.session.commit()
        flash(_("Property updated"), "success")
        return redirect(url_for("employee.properties_list"))
    return render_template("employee/property_form.html", property=prop)


@employee_bp.route("/properties/<int:prop_id>/share", methods=["GET"])  # simple redirect to public link
@login_required
@employee_required
def properties_share(prop_id: int):
    prop = Property.query.get_or_404(prop_id)
    serializer = URLSafeSerializer(current_app.config["SECRET_KEY"], salt="property-share")
    token = serializer.dumps(prop.id)
    public_url = url_for("public_property_view", token=token, _external=True)
    flash(_("Share link generated: ") + public_url, "info")
    return redirect(url_for("employee.properties_list"))


@employee_bp.route("/properties/<int:prop_id>/delete", methods=["POST"])
@login_required
@employee_required
def properties_delete(prop_id: int):
    prop = Property.query.get_or_404(prop_id)
    db.session.delete(prop)
    db.session.commit()
    flash(_("Property deleted"), "info")
    return redirect(url_for("employee.properties_list"))


# --- Apartments (units) under a Building ---


@employee_bp.route("/buildings/<int:building_id>/apartments")
@login_required
@employee_required
def apartments_list(building_id: int):
    building = Property.query.get_or_404(building_id)
    apartments = (
        Apartment.query.filter_by(building_id=building.id)
        .order_by(Apartment.created_at.desc())
        .all()
    )
    return render_template(
        "employee/apartments_list.html",
        building=building,
        apartments=apartments,
    )


@employee_bp.route("/buildings/<int:building_id>/apartments/create", methods=["GET", "POST"])
@login_required
@employee_required
def apartments_create(building_id: int):
    building = Property.query.get_or_404(building_id)
    if request.method == "POST":
        number = (request.form.get("number") or "").strip()
        floor_raw = (request.form.get("floor") or "").strip()
        area_raw = (request.form.get("area_sqm") or "").strip()
        bedrooms_raw = (request.form.get("bedrooms") or "").strip()
        bathrooms_raw = (request.form.get("bathrooms") or "").strip()
        rent_price = request.form.get("rent_price")

        floor = int(floor_raw) if floor_raw.isdigit() else None
        bedrooms = int(bedrooms_raw) if bedrooms_raw.isdigit() else None
        bathrooms = int(bathrooms_raw) if bathrooms_raw.isdigit() else None
        area_sqm = area_raw or None

        images_files = request.files.getlist("images")
        apt_images = _save_uploaded_images(images_files, "apartments")
        images_value = ",".join(apt_images) if apt_images else None

        apt = Apartment(
            building_id=building.id,
            number=number or None,
            floor=floor,
            area_sqm=area_sqm,
            bedrooms=bedrooms,
            bathrooms=bathrooms,
            rent_price=rent_price,
            status="available",
            images=images_value,
        )
        db.session.add(apt)
        db.session.commit()
        flash(_("Apartment created"), "success")
        return redirect(url_for("employee.apartments_list", building_id=building.id))
    return render_template("employee/apartment_form.html", building=building, apartment=None)


@employee_bp.route("/apartments/<int:apt_id>/edit", methods=["GET", "POST"])
@login_required
@employee_required
def apartments_edit(apt_id: int):
    apt = Apartment.query.get_or_404(apt_id)
    building = Property.query.get_or_404(apt.building_id)
    if request.method == "POST":
        apt.number = (request.form.get("number") or "").strip() or None
        floor_raw = (request.form.get("floor") or "").strip()
        area_raw = (request.form.get("area_sqm") or "").strip()
        bedrooms_raw = (request.form.get("bedrooms") or "").strip()
        bathrooms_raw = (request.form.get("bathrooms") or "").strip()
        apt.floor = int(floor_raw) if floor_raw.isdigit() else None
        apt.area_sqm = area_raw or None
        apt.bedrooms = int(bedrooms_raw) if bedrooms_raw.isdigit() else None
        apt.bathrooms = int(bathrooms_raw) if bathrooms_raw.isdigit() else None
        apt.rent_price = request.form.get("rent_price")
        apt.status = request.form.get("status") or apt.status

        images_files = request.files.getlist("images")
        if images_files:
            new_files = _save_uploaded_images(images_files, "apartments")
            if new_files:
                existing = apt.images.split(",") if apt.images else []
                apt.images = ",".join(existing + new_files)

        db.session.commit()
        flash(_("Apartment updated"), "success")
        return redirect(url_for("employee.apartments_list", building_id=building.id))
    return render_template("employee/apartment_form.html", building=building, apartment=apt)


@employee_bp.route("/apartments/<int:apt_id>/delete", methods=["POST"])
@login_required
@employee_required
def apartments_delete(apt_id: int):
    apt = Apartment.query.get_or_404(apt_id)
    building_id = apt.building_id
    db.session.delete(apt)
    db.session.commit()
    flash(_("Apartment deleted"), "info")
    return redirect(url_for("employee.apartments_list", building_id=building_id))


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


@employee_bp.route("/maintenance/<int:req_id>/update", methods=["GET", "POST"])
@login_required
@employee_required
def maintenance_update(req_id: int):
    m = MaintenanceRequest.query.get_or_404(req_id)
    if request.method == "POST":
        status = (request.form.get("status") or "").strip()
        notes = request.form.get("notes")
        allowed_statuses = {"new", "in_progress", "resolved", "closed"}
        if status and status not in allowed_statuses:
            flash(_("Invalid status"), "danger")
            return redirect(url_for("employee.maintenance_update", req_id=req_id))
        if status:
            m.status = status
        m.notes = (notes or "").strip()
        db.session.commit()
        flash(_("Maintenance request updated"), "success")
        return redirect(url_for("employee.dashboard"))
    return render_template("employee/maintenance_update.html", m=m)


@employee_bp.route("/complaints/<int:comp_id>/update", methods=["GET", "POST"])
@login_required
@employee_required
def complaint_update(comp_id: int):
    c = Complaint.query.get_or_404(comp_id)
    if request.method == "POST":
        status = (request.form.get("status") or "").strip()
        notes = request.form.get("notes")
        allowed_statuses = {"new", "reviewing", "resolved", "closed"}
        if status and status not in allowed_statuses:
            flash(_("Invalid status"), "danger")
            return redirect(url_for("employee.complaint_update", comp_id=comp_id))
        if status:
            c.status = status
        c.notes = (notes or "").strip()
        db.session.commit()
        flash(_("Complaint updated"), "success")
        return redirect(url_for("employee.dashboard"))
    return render_template("employee/complaint_update.html", c=c)
