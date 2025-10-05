import os
from flask import Flask, g, request, redirect, url_for, session, render_template, send_from_directory, abort
from flask_babel import get_locale as babel_get_locale
from .config import Config
from .extensions import db, migrate, login_manager, babel
from itsdangerous import URLSafeSerializer, BadSignature

def create_app(config_class: type = Config) -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(config_class)

    # Ensure uploads directory exists
    os.makedirs(app.config.get("UPLOAD_FOLDER", "uploads"), exist_ok=True)

    # --- Initialize Extensions ---
    # Initialize MASTER and TENANT dbs
    # MASTER holds global registry (companies, super admins)
    app.config.setdefault("SQLALCHEMY_BINDS", {})
    app.config.setdefault("SQLALCHEMY_DATABASE_URI", config_class.SQLALCHEMY_DATABASE_URI)
    app.config.setdefault("MASTER_DATABASE_URI", config_class.MASTER_DATABASE_URI)
    # Ensure on-disk SQLite directories exist for both default and master URIs
    def _ensure_sqlite_dir(uri: str) -> None:
        if isinstance(uri, str) and uri.startswith("sqlite///"):
            # Handle accidental schema like 'sqlite///' (rare)
            path = uri.replace("sqlite///", "", 1)
        elif isinstance(uri, str) and uri.startswith("sqlite:///"):
            path = uri.replace("sqlite:///", "", 1)
        else:
            return
        import os as _os
        _os.makedirs(_os.path.dirname(path), exist_ok=True)

    _ensure_sqlite_dir(app.config["SQLALCHEMY_DATABASE_URI"])
    _ensure_sqlite_dir(app.config["MASTER_DATABASE_URI"])

    # Configure master engine explicitly
    app.config["SQLALCHEMY_BINDS"]["master"] = app.config["MASTER_DATABASE_URI"]

    db.init_app(app)
    # single db instance manages both binds
    # Run migrations against TENANT db by default; master has its own simple create_all
    migrate.init_app(app, db)
    login_manager.init_app(app)
    babel.init_app(app, locale_selector=select_locale)

    # Login Manager
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    # --- Import Models after db init ---
    from .models import User, Company  # noqa: WPS433

    @login_manager.user_loader
    def load_user(user_id: str):
        return User.query.get(int(user_id))

    # --- Blueprints ---
    from .auth.routes import auth_bp
    from .admin.routes import admin_bp
    from .employee.routes import employee_bp
    from .tenant.routes import tenant_bp
    from .accountant.routes import accountant_bp
    from .superadmin.routes import superadmin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(superadmin_bp, url_prefix="/superadmin")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(employee_bp, url_prefix="/employee")
    app.register_blueprint(tenant_bp, url_prefix="/tenant")
    app.register_blueprint(accountant_bp, url_prefix="/accountant")

    # CLI commands
    from .cli import register_cli
    register_cli(app)

    # --- Context Processor ---
    @app.context_processor
    def inject_get_locale():
        return {"get_locale": lambda: str(babel_get_locale())}

    # Inject company theming into g for templates
    @app.before_request
    def inject_company_theme():
        from flask import session as flask_session
        from .models import Company
        company_id = flask_session.get("company_id")
        theme = None
        if company_id:
            company = Company.query.get(company_id)
            if company:
                theme = {
                    "name": company.name,
                    "logo_path": company.logo_path,
                    "primary_color": company.primary_color,
                    "secondary_color": company.secondary_color,
                    "font_family": company.font_family,
                }
        g.company_theme = theme

    # --- Routes ---
    @app.route("/")
    def index():
        from flask_login import current_user

        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        role_redirect = {
            "superadmin": "superadmin.dashboard",
            "admin": "admin.dashboard",
            "employee": "employee.dashboard",
            "tenant": "tenant.dashboard",
            "accountant": "accountant.dashboard",
        }
        return redirect(url_for(role_redirect.get(current_user.role, "auth.login")))

    # --- Tenancy binding per request ---
    @app.before_request
    def bind_tenant_database():
        """Bind the tenant engine to db.session based on selected company in session.

        Strategy:
        - Read company id from session (or subdomain header in future)
        - Load Company from master DB
        - Reflect/ensure SQLAlchemy has an engine for that URI
        - Re-bind db.engines[None] to the tenant engine for this app context
        """
        from flask import session as flask_session
        from sqlalchemy import create_engine
        company_id = flask_session.get("company_id")
        # Ensure master bind exists
        engines = db.engines  # type: ignore[attr-defined]
        engines["master"]  # ensure master engine is initialized
        if not company_id:
            # No tenant selected → restore global default engine
            global_engine = engines.get("__global__")
            if global_engine is not None:
                engines[None] = global_engine
            return
        company = Company.query.get(company_id)
        if not company or not company.is_active or company.is_archived:
            # Invalid tenant selection → restore global default engine
            global_engine = engines.get("__global__")
            if global_engine is not None:
                engines[None] = global_engine
            return
        uri = company.db_uri
        # Create or reuse an engine for this tenant under bind key = company.subdomain
        bind_key = company.subdomain
        if bind_key not in engines:
            engines[bind_key] = create_engine(uri, pool_pre_ping=True)
        # Point the default engine to this tenant for ORM operations
        engines[None] = engines[bind_key]
        # Ensure all tenant-bound tables exist (first-run convenience)
        try:
            from sqlalchemy import inspect as sa_inspect
            inspector = sa_inspect(engines[None])
            # Heuristic: if no 'users' table, create all
            if not inspector.has_table('users'):
                prev = None
                try:
                    prev = engines.get(None)
                    engines[None] = engines[bind_key]
                    db.create_all()
                finally:
                    if prev is not None:
                        engines[None] = prev
        except Exception:
            pass

    @app.route("/set-lang/<lang_code>")
    def set_language(lang_code: str):
        if lang_code in app.config.get("LANGUAGES", {}):
            session["lang"] = lang_code
        return redirect(request.referrer or url_for("index"))

    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename: str):
        upload_folder = app.config.get("UPLOAD_FOLDER", "uploads")
        return send_from_directory(upload_folder, filename, as_attachment=False)

    # --- Initialize master tables if not present ---
    with app.app_context():
        try:
            # Create only master-bound tables (e.g., Company)
            db.create_all(bind="master")
        except Exception:
            pass

        # Ensure default tenant tables exist on first run (when no company bound)
        # This prevents "no such table: users" before any migrations run
        try:
            from sqlalchemy import inspect as sa_inspect
            inspector = sa_inspect(db.engines[None])  # ensure default engine exists
            if not inspector.has_table('users'):
                db.create_all()
        except Exception:
            pass

        # Capture and cache the global default engine so we can restore it
        # on requests where no tenant is selected. Do this after ensuring the
        # default engine has been realized by SQLAlchemy.
        try:
            engines = db.engines  # type: ignore[attr-defined]
            _ = engines[None]
            engines["__global__"] = engines[None]
        except Exception:
            pass

    # --- Public Share Route for Property Details ---
    def _get_property_share_serializer() -> URLSafeSerializer:
        secret_key = app.config.get("SECRET_KEY")
        return URLSafeSerializer(secret_key, salt="property-share")

    @app.route("/p/<token>")
    def public_property_view(token: str):
        try:
            serializer = _get_property_share_serializer()
            property_id = serializer.loads(token)
        except BadSignature:
            return abort(404)

        from .models import Property  # local import to avoid circulars

        prop = Property.query.get_or_404(int(property_id))

        # Prepare images list from stored comma-separated paths
        images = []
        if prop.images:
            images = [p.strip() for p in prop.images.split(",") if p.strip()]

        return render_template(
            "public/property_view.html",
            prop=prop,
            images=images,
        )

    # --- Error Handlers ---
    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("403.html"), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("404.html"), 404

    return app


# --- Helper Functions ---
def select_locale():
    """Return the selected locale from session or default."""
    from flask import session, request
    lang = session.get("lang")
    if lang:
        return lang
    return request.accept_languages.best_match(Config.LANGUAGES.keys())
