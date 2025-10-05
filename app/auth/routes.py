from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app, abort
from flask_login import login_user, logout_user, login_required
from flask_babel import gettext as _
from ..extensions import db
from ..models import User, Company
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        # أولا: تحقق من المدير العام
        user = User.query.filter_by(username=username, role="superadmin").first()
        if user and user.check_password(password):
            login_user(user)
            flash(_("Welcome back, Super Admin %(user)s", user=user.username), "success")
            return redirect(url_for("superadmin.dashboard"))  # ← هنا التوجيه الصحيح

        # ثانيا: تحقق من المستخدمين داخل الشركات
        active_companies = (
            Company.query.filter_by(is_archived=False, is_active=True)
            .order_by(Company.created_at.asc())
            .all()
        )
        from flask import session as flask_session
        from sqlalchemy import create_engine
        engines = db.engines  # type: ignore[attr-defined]
        previous_default = engines.get(None)
        try:
            for c in active_companies:
                engine = engines.get(c.subdomain)
                if engine is None:
                    engine = create_engine(c.db_uri, pool_pre_ping=True)
                    engines[c.subdomain] = engine
                engines[None] = engine
                user = User.query.filter_by(username=username).first()
                if user and user.check_password(password):
                    flask_session["company_id"] = c.id
                    login_user(user)
                    flash(_("Welcome back, %(user)s", user=user.username), "success")
                    return redirect(url_for("index"))  # ← هنا مدير الشركة أو باقي المستخدمين
        finally:
            if previous_default is not None:
                engines[None] = previous_default

        flash(_("Invalid credentials"), "danger")

    return render_template("auth/login.html")



@auth_bp.route("/logout")
@login_required
def logout():
    from flask import session as flask_session
    logout_user()
    # Clear company binding on logout
    flask_session.pop("company_id", None)
    flash(_("You have been logged out"), "info")
    return redirect(url_for("auth.login"))


def _get_company_setup_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config.get("SECRET_KEY"), salt="company-setup")


@auth_bp.route("/setup/<token>", methods=["GET", "POST"])
def company_setup(token: str):
    # Validate token and get company id
    try:
        serializer = _get_company_setup_serializer()
        company_id = serializer.loads(token, max_age=60 * 60 * 24 * 7)  # 7 days
    except SignatureExpired:
        flash(_("Setup link expired. Ask your administrator for a new link."), "warning")
        return redirect(url_for("auth.login"))
    except BadSignature:
        return abort(404)

    company = Company.query.get_or_404(int(company_id))

    # If an admin already exists in this company's DB, skip setup
    try:
        from sqlalchemy import create_engine
        engines = db.engines  # type: ignore[attr-defined]
        prev_default = engines.get(None)
        bind_key = company.subdomain
        if bind_key not in engines:
            engines[bind_key] = create_engine(company.db_uri, pool_pre_ping=True)
        engines[None] = engines[bind_key]
        if User.query.filter_by(role="admin").first():
            flash(_("Setup already completed for this company. Please log in."), "info")
            if prev_default is not None:
                engines[None] = prev_default
            return redirect(url_for("auth.login"))
    except Exception:
        # If any error occurs during check, proceed to form
        pass

    # Allow manager to set up initial admin account bound to this company DB
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        password2 = request.form.get("password2") or ""
        phone = (request.form.get("phone") or "").strip()

        if not username or not password:
            flash(_("Username and password are required"), "warning")
            return render_template("auth/company_setup.html", company=company)
        if password != password2:
            flash(_("Passwords do not match"), "warning")
            return render_template("auth/company_setup.html", company=company)

        # Bind tenant DB to create the admin user in that company's database
        from sqlalchemy import create_engine
        engines = db.engines  # type: ignore[attr-defined]
        prev_default = engines.get(None)
        try:
            bind_key = company.subdomain
            if bind_key not in engines:
                engines[bind_key] = create_engine(company.db_uri, pool_pre_ping=True)
            engines[None] = engines[bind_key]

            # Create admin user if not exists
            existing = User.query.filter_by(username=username).first()
            if existing:
                flash(_("Username already exists"), "danger")
                return render_template("auth/company_setup.html", company=company)

            admin = User(username=username, role="admin", phone=phone)
            admin.set_password(password)
            db.session.add(admin)
            db.session.commit()

            flash(_("Admin account created. You can now log in."), "success")
            return redirect(url_for("auth.login"))
        finally:
            if prev_default is not None:
                engines[None] = prev_default

    return render_template("auth/company_setup.html", company=company)

