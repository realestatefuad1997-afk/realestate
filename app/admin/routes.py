from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from flask_babel import gettext as _
from ..models import Property, Contract, Payment, User, Apartment
from ..extensions import db
from flask import request, redirect, url_for, flash
from datetime import date, datetime, timedelta
from sqlalchemy import text


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
    # Basic counts for employees and tenants
    total_employees = User.query.filter_by(role="employee").count()
    total_tenants = User.query.filter_by(role="tenant").count()

    return render_template(
        "admin/dashboard.html",
        properties_count=properties_count,
        active_contracts=active_contracts,
        total_income=total_income,
        total_expenses=total_expenses,
        profit=profit,
        unleased_properties=unleased_properties,
        overdue_maintenance_24h=overdue_maintenance_24h,
        total_employees=total_employees,
        total_tenants=total_tenants,
    )


@admin_bp.route("/users")
@login_required
@admin_required
def users_list():
    from ..models import User
    # Optional role filter via query string, e.g., /admin/users?role=tenant
    role = (request.args.get("role") or "").strip().lower()
    query = User.query
    if role in {"employee", "tenant", "accountant", "admin"}:
        query = query.filter_by(role=role)
    users = query.order_by(User.created_at.desc()).all()
    return render_template("admin/users_list.html", users=users)


@admin_bp.route("/users/new/<role>", methods=["GET", "POST"])
@login_required
@admin_required
def create_user(role: str):
    from flask import abort

    allowed_roles = ("employee", "tenant")
    if role not in allowed_roles:
        return abort(404)

    # For tenants, list all buildings, plus standalone apartments that are not under an active contract
    available_properties = []
    if role == "tenant":
        today = date.today()
        # Standalone apartments with no active contract
        active_apartment_props_subq = (
            db.session.query(Contract.property_id)
            .filter(
                Contract.status == "active",
                Contract.start_date <= today,
                Contract.end_date >= today,
            )
            .subquery()
        )
        standalone_apartments = (
            Property.query.filter(Property.property_type == "apartment", ~Property.id.in_(active_apartment_props_subq))
            .order_by(Property.created_at.desc())
            .all()
        )
        buildings = (
            Property.query.filter(Property.property_type == "building")
            .order_by(Property.created_at.desc())
            .all()
        )
        available_properties = buildings + standalone_apartments

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = (request.form.get("email", "").strip() or None)
        phone = (request.form.get("phone", "").strip() or None)
        password = request.form.get("password", "")
        selected_property_id = (request.form.get("property_id") or "").strip()
        selected_apartment_id = (request.form.get("apartment_id") or "").strip()

        # Basic required validation
        if role == "employee":
            if not username or not email or not password:
                flash(_("All fields are required"), "warning")
                return render_template(
                    "admin/user_form.html",
                    role=role,
                    username_value=username,
                    email_value=email or "",
                    properties=None,
                )
        else:  # tenant
            if not username or not phone or not password or not selected_property_id:
                flash(_("All fields are required"), "warning")
                return render_template(
                    "admin/user_form.html",
                    role=role,
                    username_value=username,
                    phone_value=phone or "",
                    properties=available_properties,
                    selected_property_id=selected_property_id,
                    selected_apartment_id=selected_apartment_id,
                )

        # Uniqueness validation
        from sqlalchemy import or_
        conditions = [User.username == username]
        if role == "employee":
            if email:
                conditions.append(User.email == email)
        else:
            if phone:
                conditions.append(User.phone == phone)
            if email:
                conditions.append(User.email == email)
        existing_user = User.query.filter(or_(*conditions)).first()
        if existing_user:
            flash(_("Username or email already exists") if role == "employee" else _("Username or phone already exists"), "danger")
            return render_template(
                "admin/user_form.html",
                role=role,
                username_value=username,
                email_value=email or "",
                phone_value=phone or "",
                properties=available_properties if role == "tenant" else None,
                selected_property_id=selected_property_id,
                selected_apartment_id=selected_apartment_id,
            )

        # For tenants, ensure property (and apartment if building) are valid
        property_obj = None
        apartment_obj = None
        if role == "tenant":
            try:
                pid_int = int(selected_property_id)
            except ValueError:
                flash(_("Invalid property selected"), "danger")
                return render_template(
                    "admin/user_form.html",
                    role=role,
                    username_value=username,
                    phone_value=phone or "",
                    properties=available_properties,
                    selected_property_id=selected_property_id,
                    selected_apartment_id=selected_apartment_id,
                )
            property_obj = Property.query.get(pid_int)
            if property_obj is None:
                flash(_("Invalid property selected"), "danger")
                return render_template(
                    "admin/user_form.html",
                    role=role,
                    username_value=username,
                    phone_value=phone or "",
                    properties=available_properties,
                    selected_property_id=selected_property_id,
                    selected_apartment_id=selected_apartment_id,
                )
            if property_obj.property_type == "building":
                if not selected_apartment_id:
                    flash(_("Please select an apartment"), "warning")
                    return render_template(
                        "admin/user_form.html",
                        role=role,
                        username_value=username,
                        phone_value=phone or "",
                        properties=available_properties,
                        selected_property_id=selected_property_id,
                        selected_apartment_id=selected_apartment_id,
                    )
                try:
                    aid_int = int(selected_apartment_id)
                except ValueError:
                    flash(_("Invalid apartment selected"), "danger")
                    return render_template(
                        "admin/user_form.html",
                        role=role,
                        username_value=username,
                        phone_value=phone or "",
                        properties=available_properties,
                        selected_property_id=selected_property_id,
                        selected_apartment_id=selected_apartment_id,
                    )
                apartment_obj = Apartment.query.filter_by(id=aid_int, building_id=property_obj.id).first()
                if apartment_obj is None or (apartment_obj.status or "").lower() != "available":
                    flash(_("Selected apartment is no longer available"), "danger")
                    return render_template(
                        "admin/user_form.html",
                        role=role,
                        username_value=username,
                        phone_value=phone or "",
                        properties=available_properties,
                        selected_property_id=selected_property_id,
                        selected_apartment_id=selected_apartment_id,
                    )
            else:
                # Standalone apartment must still be available (no active contract)
                today = date.today()
                active_for_prop = (
                    Contract.query.filter(
                        Contract.property_id == property_obj.id,
                        Contract.status == "active",
                        Contract.start_date <= today,
                        Contract.end_date >= today,
                    ).first()
                )
                if active_for_prop is not None:
                    flash(_("Selected property is no longer available"), "danger")
                    return render_template(
                        "admin/user_form.html",
                        role=role,
                        username_value=username,
                        phone_value=phone or "",
                        properties=available_properties,
                        selected_property_id=selected_property_id,
                    )

        # Create user
        if role == "employee":
            new_user = User(username=username, email=email, role=role)
        else:
            new_user = User(username=username, phone=phone, email=email, role=role)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        if role == "employee":
            flash(_("Employee created successfully"), "success")
        else:
            # Auto-create a contract for the selected property (and apartment if building)
            start_date = date.today()
            end_date = start_date + timedelta(days=365)
            rent_amount = None
            apt_id_val = None
            if property_obj.property_type == "building" and apartment_obj is not None:
                rent_amount = apartment_obj.rent_price or 0
                apt_id_val = apartment_obj.id
            else:
                rent_amount = property_obj.price or 0

            contract = Contract(
                property_id=property_obj.id,
                apartment_id=apt_id_val,
                tenant_id=new_user.id,
                start_date=start_date,
                end_date=end_date,
                rent_amount=rent_amount,
                status="active",
            )
            db.session.add(contract)
            # Update statuses
            try:
                if apartment_obj is not None:
                    apartment_obj.status = "occupied"
                else:
                    property_obj.status = "leased"
            except Exception:
                pass
            db.session.commit()
            flash(_("Tenant and contract created successfully"), "success")
        return redirect(url_for("admin.users_list"))

    return render_template(
        "admin/user_form.html",
        role=role,
        properties=available_properties if role == "tenant" else None,
    )


# --- API: Apartments under a Building (JSON) ---
@admin_bp.route("/api/buildings/<int:building_id>/apartments")
@login_required
@admin_required
def api_building_apartments(building_id: int):
    status_filter = (request.args.get("status") or "").strip().lower()
    apartments_q = Apartment.query.filter_by(building_id=building_id)
    apartments = apartments_q.order_by(Apartment.number.asc()).all()
    if status_filter:
        apartments = [a for a in apartments if (a.status or "").lower() == status_filter]
    def to_label(a: Apartment) -> str:
        rent = (a.rent_price if a.rent_price is not None else "-")
        num = a.number or str(a.id)
        return f"#{num} — {str(rent)}"
    return jsonify([
        {
            "id": a.id,
            "label": to_label(a),
            "number": a.number,
            "status": a.status,
            "rent_price": str(a.rent_price) if a.rent_price is not None else None,
        }
        for a in apartments
    ])

