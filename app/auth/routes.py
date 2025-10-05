from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required
from flask_babel import gettext as _
from ..extensions import db
from ..models import User, Company


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

