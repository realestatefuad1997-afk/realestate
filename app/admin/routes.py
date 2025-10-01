from flask import Blueprint, render_template
from flask_login import login_required, current_user
from flask_babel import gettext as _
from ..models import Property, Contract, Payment, User
from ..extensions import db
from flask import request, redirect, url_for, flash


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
    active_contracts = Contract.query.filter_by(status="active").count()
    total_revenue = (
        Payment.query.filter_by(status="paid")
        .with_entities(db.func.coalesce(db.func.sum(Payment.amount), 0))
        .scalar()
    )
    return render_template(
        "admin/dashboard.html",
        properties_count=properties_count,
        active_contracts=active_contracts,
        total_revenue=total_revenue,
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

        if not username or not email or not password:
            flash(_("All fields are required"), "warning")
            return render_template(
                "admin/user_form.html",
                role=role,
                username_value=username,
                email_value=email,
            )

        # ensure unique username/email
        existing_user = (
            User.query.filter((User.username == username) | (User.email == email)).first()
        )
        if existing_user:
            flash(_("Username or email already exists"), "danger")
            return render_template(
                "admin/user_form.html",
                role=role,
                username_value=username,
                email_value=email,
            )

        new_user = User(username=username, email=email, role=role)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        if role == "employee":
            flash(_("Employee created successfully"), "success")
        else:
            flash(_("Tenant created successfully"), "success")
        return redirect(url_for("admin.users_list"))

    return render_template("admin/user_form.html", role=role)

