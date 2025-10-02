import os
from flask import Flask, g, request, redirect, url_for, session, render_template, send_from_directory
from itsdangerous import URLSafeSerializer
from flask_babel import get_locale as babel_get_locale
from .config import Config
from .extensions import db, migrate, login_manager, babel


def create_app(config_class: type = Config) -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(config_class)

    # Ensure instance and uploads directories exist
    os.makedirs(os.path.dirname(app.config.get("SQLALCHEMY_DATABASE_URI", "sqlite:////workspace/instance/app.db").replace("sqlite:////", "/")), exist_ok=True)
    os.makedirs(app.config.get("UPLOAD_FOLDER", "/workspace/uploads"), exist_ok=True)

    # Init extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    def select_locale():
        lang = session.get("lang")
        if lang:
            return lang
        return request.accept_languages.best_match(app.config.get("LANGUAGES", {}).keys())

    babel.init_app(app, locale_selector=select_locale)

    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    from .models import User  # noqa: WPS433 (import here to register models)

    @login_manager.user_loader
    def load_user(user_id: str):
        return User.query.get(int(user_id))

    # Locale selection
    # locale selector configured above

    # Blueprints
    from .auth.routes import auth_bp
    from .admin.routes import admin_bp
    from .employee.routes import employee_bp
    from .tenant.routes import tenant_bp
    from .accountant.routes import accountant_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(employee_bp, url_prefix="/employee")
    app.register_blueprint(tenant_bp, url_prefix="/tenant")
    app.register_blueprint(accountant_bp, url_prefix="/accountant")

    # CLI
    from .cli import register_cli

    register_cli(app)

    @app.context_processor
    def inject_get_locale():
        # Expose get_locale() to Jinja templates as a callable returning a string like 'en' or 'ar'
        def _get_locale():
            return str(babel_get_locale())

        return {"get_locale": _get_locale}

    # --- Property share link utilities (token-based, no DB changes) ---
    def _get_share_serializer() -> URLSafeSerializer:
        return URLSafeSerializer(app.config["SECRET_KEY"], salt="property-share")

    @app.context_processor
    def inject_share_link_helpers():
        def generate_property_share_token(property_id: int) -> str:
            serializer = _get_share_serializer()
            return serializer.dumps({"property_id": int(property_id)})

        def property_share_url(property_id: int) -> str:
            token = generate_property_share_token(property_id)
            return url_for("public_property", token=token, _external=True)

        return {
            "generate_property_share_token": generate_property_share_token,
            "property_share_url": property_share_url,
        }

    @app.route("/")
    def index():
        # Redirect based on role
        from flask_login import current_user

        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if current_user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        if current_user.role == "employee":
            return redirect(url_for("employee.dashboard"))
        if current_user.role == "tenant":
            return redirect(url_for("tenant.dashboard"))
        if current_user.role == "accountant":
            return redirect(url_for("accountant.dashboard"))
        return redirect(url_for("auth.login"))

    @app.route("/public/property/<token>")
    def public_property(token: str):
        serializer = _get_share_serializer()
        try:
            data = serializer.loads(token)
            prop_id = int(data.get("property_id"))
        except Exception:
            return (render_template("404.html"), 404)

        from .models import Property

        prop = Property.query.get_or_404(prop_id)
        return render_template("public/property_detail.html", property=prop)

    @app.route("/set-lang/<lang_code>")
    def set_language(lang_code: str):
        if lang_code in app.config.get("LANGUAGES", {}).keys():
            session["lang"] = lang_code
        return redirect(request.referrer or url_for("index"))

    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename: str):
        upload_folder = app.config.get("UPLOAD_FOLDER")
        return send_from_directory(upload_folder, filename, as_attachment=False)

    # Error handlers
    @app.errorhandler(403)
    def forbidden(_e):
        return (render_template("403.html"), 403)

    @app.errorhandler(404)
    def not_found(_e):
        return (render_template("404.html"), 404)

    return app
