from __future__ import annotations

import os
import datetime
from flask import render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required, current_user
from sqlalchemy import text

from ..extensions import db
from ..models import Company
from ..tenant_manager import TenantManager
from . import superadmin_bp


def superadmin_required(func):
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or (current_user.role or "").lower() != "admin":
            from flask import abort
            return abort(403)
        return func(*args, **kwargs)

    return wrapper


@superadmin_bp.route("/")
@login_required
@superadmin_required
def dashboard():
    companies = Company.query.order_by(Company.created_at.desc()).all()
    # Basic cross-company stats (counts) by connecting to each company's DB
    tm = TenantManager()
    stats = []
    for c in companies:
        try:
            from sqlalchemy import create_engine
            engine = create_engine(c.db_uri)
            with engine.connect() as conn:
                properties = conn.execute(text("SELECT COUNT(1) FROM properties")).scalar() if _has_table(conn, "properties") else 0
                tenants = conn.execute(text("SELECT COUNT(1) FROM users WHERE role='tenant'" )).scalar() if _has_table(conn, "users") else 0
                contracts = conn.execute(text("SELECT COUNT(1) FROM contracts")).scalar() if _has_table(conn, "contracts") else 0
            stats.append({"company": c, "properties": properties, "tenants": tenants, "contracts": contracts})
        except Exception:
            stats.append({"company": c, "properties": 0, "tenants": 0, "contracts": 0})
    return render_template("superadmin/dashboard.html", stats=stats)


def _has_table(conn, table_name: str) -> bool:
    try:
        res = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"), {"t": table_name})
        return res.first() is not None
    except Exception:
        return False


@superadmin_bp.route("/companies")
@login_required
@superadmin_required
def companies_list():
    companies = Company.query.order_by(Company.name.asc()).all()
    return render_template("superadmin/companies_list.html", companies=companies)


@superadmin_bp.route("/companies/new", methods=["GET", "POST"])
@login_required
@superadmin_required
def company_create():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        subdomain = (request.form.get("subdomain") or "").strip().lower()
        primary = (request.form.get("primary_color") or "#0d6efd").strip()
        secondary = (request.form.get("secondary_color") or "#6c757d").strip()
        font_family = (request.form.get("font_family") or "system-ui, -apple-system, Segoe UI, Roboto").strip()
        custom_uri = (request.form.get("db_uri") or "").strip()

        if not name or not subdomain:
            flash("Name and subdomain are required", "warning")
            return render_template("superadmin/company_form.html")

        tm = TenantManager()
        spec = tm.build_sqlite_uri(subdomain) if not custom_uri else None
        db_uri = custom_uri or spec.uri  # type: ignore[union-attr]

        # Create company record in master
        c = Company(
            name=name,
            subdomain=subdomain,
            db_uri=db_uri,
            primary_color=primary,
            secondary_color=secondary,
            font_family=font_family,
        )
        db.session.add(c)
        db.session.commit()

        # Ensure tenant DB exists and create schema
        _provision_tenant_db(db_uri)

        flash("Company created and database provisioned", "success")
        return redirect(url_for("superadmin.companies_list"))

    return render_template("superadmin/company_form.html")


@superadmin_bp.route("/companies/<int:company_id>/edit", methods=["GET", "POST"])
@login_required
@superadmin_required
def company_edit(company_id: int):
    company = Company.query.get_or_404(company_id)
    if request.method == "POST":
        company.name = (request.form.get("name") or company.name).strip()
        company.primary_color = (request.form.get("primary_color") or company.primary_color).strip()
        company.secondary_color = (request.form.get("secondary_color") or company.secondary_color).strip()
        company.font_family = (request.form.get("font_family") or company.font_family).strip()
        company.is_active = bool(request.form.get("is_active"))
        company.is_archived = bool(request.form.get("is_archived"))
        db.session.commit()
        flash("Company updated", "success")
        return redirect(url_for("superadmin.companies_list"))
    return render_template("superadmin/company_form.html", company=company)


@superadmin_bp.route("/companies/<int:company_id>/export")
@login_required
@superadmin_required
def company_export(company_id: int):
    company = Company.query.get_or_404(company_id)
    tm = TenantManager()
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
    export_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backups"))
    os.makedirs(export_dir, exist_ok=True)
    out_path = os.path.join(export_dir, f"{company.subdomain}_{timestamp}.db")
    try:
        if company.db_uri.startswith("sqlite"):  # Use VACUUM INTO export
            tm.export_sqlite(company.db_uri, out_path)
            return send_file(out_path, as_attachment=True)
        else:
            flash("Export for non-SQLite is not configured here; use CLI", "info")
            return redirect(url_for("superadmin.companies_list"))
    except Exception as exc:
        flash(f"Export failed: {exc}", "danger")
        return redirect(url_for("superadmin.companies_list"))


@superadmin_bp.route("/companies/<int:company_id>/delete", methods=["POST"]) 
@login_required
@superadmin_required
def company_delete(company_id: int):
    company = Company.query.get_or_404(company_id)
    db_uri = company.db_uri
    db.session.delete(company)
    db.session.commit()
    # Remove tenant DB if SQLite
    try:
        tm = TenantManager()
        if db_uri.startswith("sqlite"): 
            tm.delete_sqlite(db_uri)
        flash("Company and database deleted", "success")
    except Exception:
        flash("Company deleted, but database file could not be removed", "warning")
    return redirect(url_for("superadmin.companies_list"))


def _provision_tenant_db(db_uri: str) -> None:
    """Create schema in a new tenant DB by temporarily binding engine to ORM."""
    from sqlalchemy import create_engine
    engine = create_engine(db_uri, pool_pre_ping=True)
    # Temporarily bind db default engine to the tenant engine, then create_all
    from ..extensions import db as tenant_db
    engines = tenant_db.engines  # type: ignore[attr-defined]
    previous_default = engines.get(None)
    engines[None] = engine
    try:
        tenant_db.create_all()
    finally:
        if previous_default is not None:
            engines[None] = previous_default
