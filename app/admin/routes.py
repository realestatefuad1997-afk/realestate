from flask import Blueprint, render_template
from flask_login import login_required, current_user
from flask_babel import gettext as _
from ..models import Property, Contract, Payment, User
from ..extensions import db
from flask import request, redirect, url_for, flash
from datetime import date, datetime, timedelta
from sqlalchemy import text
from flask import current_app
from werkzeug.utils import secure_filename
import os


admin_bp = Blueprint("admin", __name__)


def admin_required(func):
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            from flask import abort

            return abort(403)
        return func(*args, **kwargs)

    return wrapper


@admin_bp.route("/")
@login_required
@admin_required
def dashboard():
    properties_count = Property.query.count()
    # Active contracts overall (legacy metric kept)
    active_contracts = Contract.query.filter_by(status="active").count()

    # Income (paid payments)
    total_income = (
        Payment.query.filter_by(status="paid")
        .with_entities(db.func.coalesce(db.func.sum(Payment.amount), 0))
        .scalar()
    )

    # Expenses (optional table). If table doesn't exist, default to 0
    total_expenses = 0
    try:
        inspector = db.inspect(db.engine)
        if inspector.has_table("expenses"):
            res = db.session.execute(text("SELECT COALESCE(SUM(amount), 0) FROM expenses"))
            total_expenses = res.scalar() or 0
    except Exception:
        total_expenses = 0

    # Profit = income - expenses
    profit = (total_income or 0) - (total_expenses or 0)

    # Unleased properties: properties with no active contract covering today
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
    unleased_properties = (
        db.session.query(db.func.count(Property.id))
        .filter(~Property.id.in_(active_props_subq))
        .scalar()
    )

    # Maintenance requests older than 24 hours (optional table)
    overdue_maintenance_24h = 0
    try:
        # reuse inspector if created above; create if not
        if 'inspector' not in locals():
            inspector = db.inspect(db.engine)
        if inspector.has_table("maintenance_requests"):
            threshold = datetime.utcnow() - timedelta(hours=24)
            res = db.session.execute(
                text(
                    """
                    SELECT COUNT(1)
                    FROM maintenance_requests
                    WHERE (status IS NULL OR status NOT IN ('resolved','closed','done'))
                      AND created_at <= :threshold
                    """
                ),
                {"threshold": threshold},
            )
            overdue_maintenance_24h = res.scalar() or 0
    except Exception:
        overdue_maintenance_24h = 0
    return render_template(
        "admin/dashboard.html",
        properties_count=properties_count,
        active_contracts=active_contracts,
        total_income=total_income,
        total_expenses=total_expenses,
        profit=profit,
        unleased_properties=unleased_properties,
        overdue_maintenance_24h=overdue_maintenance_24h,
    )


@admin_bp.route("/users")
@login_required
@admin_required
def users_list():
    from ..models import User

    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin/users_list.html", users=users)


@admin_bp.route("/users/new/<role>", methods=["GET", "POST"])
@login_required
@admin_required
def create_user(role: str):
    from flask import abort

    allowed_roles = ("employee", "tenant")
    if role not in allowed_roles:
        return abort(404)

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        # Tenant-specific fields
        property_id_raw = request.form.get("property_id", "").strip()
        rent_amount_raw = request.form.get("rent_amount", "").strip()

        if not username or not email or not password:
            flash(_("All fields are required"), "warning")
            props = Property.query.all() if role == "tenant" else None
            return render_template(
                "admin/user_form.html",
                role=role,
                username_value=username,
                email_value=email,
                properties=props,
                property_id_value=property_id_raw,
                rent_amount_value=rent_amount_raw,
            )

        # ensure unique username/email
        existing_user = (
            User.query.filter((User.username == username) | (User.email == email)).first()
        )
        if existing_user:
            flash(_("Username or email already exists"), "danger")
            props = Property.query.all() if role == "tenant" else None
            return render_template(
                "admin/user_form.html",
                role=role,
                username_value=username,
                email_value=email,
                properties=props,
                property_id_value=property_id_raw,
                rent_amount_value=rent_amount_raw,
            )

        # Create user (and contract if tenant) in one transaction
        try:
            new_user = User(username=username, email=email, role=role)
            new_user.set_password(password)
            db.session.add(new_user)

            if role == "tenant":
                # Validate tenant-specific inputs
                if not property_id_raw or not rent_amount_raw:
                    raise ValueError("PROPERTY_AND_RENT_REQUIRED")
                try:
                    property_id = int(property_id_raw)
                except Exception:
                    raise ValueError("INVALID_PROPERTY")
                try:
                    rent_value = float(rent_amount_raw)
                except Exception:
                    raise ValueError("INVALID_RENT")
                if rent_value <= 0:
                    raise ValueError("INVALID_RENT")

                prop = Property.query.get(property_id)
                if not prop:
                    raise ValueError("INVALID_PROPERTY")

                # Ensure property has no active contract covering today
                today = date.today()
                overlapping = (
                    Contract.query.filter(
                        Contract.property_id == property_id,
                        Contract.status == "active",
                        Contract.start_date <= today,
                        Contract.end_date >= today,
                    ).first()
                )
                if overlapping:
                    raise ValueError("PROPERTY_UNAVAILABLE")

                # Create 1-year contract starting today
                contract = Contract(
                    property_id=property_id,
                    tenant=new_user,
                    start_date=today,
                    end_date=today + timedelta(days=365),
                    rent_amount=rent_value,
                    status="active",
                )
                db.session.add(contract)

            db.session.commit()
            if role == "employee":
                flash(_("Employee created successfully"), "success")
            else:
                flash(_("Tenant created successfully"), "success")
            return redirect(url_for("admin.users_list"))
        except ValueError as ve:
            db.session.rollback()
            code = str(ve)
            if code == "PROPERTY_AND_RENT_REQUIRED":
                flash(_("Property and rent are required for tenants"), "warning")
            elif code == "INVALID_PROPERTY":
                flash(_("Please select a valid property"), "warning")
            elif code == "INVALID_RENT":
                flash(_("Please enter a valid positive rent amount"), "warning")
            elif code == "PROPERTY_UNAVAILABLE":
                flash(_("Selected property already has an active contract"), "danger")
            else:
                flash(_("Failed to create tenant"), "danger")
            props = Property.query.all() if role == "tenant" else None
            return render_template(
                "admin/user_form.html",
                role=role,
                username_value=username,
                email_value=email,
                properties=props,
                property_id_value=property_id_raw,
                rent_amount_value=rent_amount_raw,
            )
        except Exception:
            db.session.rollback()
            flash(_("An unexpected error occurred"), "danger")
            props = Property.query.all() if role == "tenant" else None
            return render_template(
                "admin/user_form.html",
                role=role,
                username_value=username,
                email_value=email,
                properties=props,
                property_id_value=property_id_raw,
                rent_amount_value=rent_amount_raw,
            )

    # GET
    if role == "tenant":
        props = Property.query.all()
        return render_template("admin/user_form.html", role=role, properties=props)
    return render_template("admin/user_form.html", role=role)


@admin_bp.route("/properties")
@login_required
@admin_required
def properties_list():
    properties = Property.query.order_by(Property.created_at.desc()).all()
    return render_template("admin/properties_list.html", properties=properties)


@admin_bp.route("/properties/create", methods=["GET", "POST"])
@login_required
@admin_required
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
        flash(_( "Property created"), "success")
        return redirect(url_for("admin.properties_list"))
    return render_template("admin/property_form.html", property=None)

