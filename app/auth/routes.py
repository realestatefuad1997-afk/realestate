from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required
from flask_babel import gettext as _
from ..extensions import db
from ..models import User, Company


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    # Load companies for selection (from master DB)
    companies = Company.query.filter_by(is_archived=False, is_active=True).order_by(Company.name.asc()).all()
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        company_id = (request.form.get("company_id") or "").strip()
        # Validate company selection
        selected_company = Company.query.filter_by(id=int(company_id) if company_id.isdigit() else None).first()
        if not selected_company:
            flash(_("Please select a company"), "warning")
            return render_template("auth/login.html", companies=companies)
        # Bind chosen company in session, then authenticate
        from flask import session as flask_session
        flask_session["company_id"] = selected_company.id
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash(_("Welcome back, %(user)s", user=user.username), "success")
            next_url = request.args.get("next") or url_for("index")
            return redirect(next_url)
        flash(_("Invalid credentials"), "danger")
    return render_template("auth/login.html", companies=companies)


@auth_bp.route("/logout")
@login_required
def logout():
    from flask import session as flask_session
    logout_user()
    # Clear company binding on logout
    flask_session.pop("company_id", None)
    flash(_("You have been logged out"), "info")
    return redirect(url_for("auth.login"))

