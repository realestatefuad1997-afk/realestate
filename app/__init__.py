import os
from flask import Flask, g, request, redirect, url_for, session, render_template, send_from_directory
from babel.messages.pofile import read_po
from babel.messages.mofile import write_mo
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

    # Compile .po to .mo on startup if needed so new translations take effect
    def _compile_translations_if_needed() -> None:
        try:
            translations_dir = os.path.join(os.path.dirname(__file__), "translations")
            if not os.path.isdir(translations_dir):
                return
            for lang_code in os.listdir(translations_dir):
                lc_messages_dir = os.path.join(translations_dir, lang_code, "LC_MESSAGES")
                po_path = os.path.join(lc_messages_dir, "messages.po")
                mo_path = os.path.join(lc_messages_dir, "messages.mo")
                if not os.path.isfile(po_path):
                    continue
                po_mtime = os.path.getmtime(po_path)
                mo_mtime = os.path.getmtime(mo_path) if os.path.exists(mo_path) else -1
                if mo_mtime < po_mtime:
                    with open(po_path, "r", encoding="utf-8") as po_file:
                        catalog = read_po(po_file)
                    os.makedirs(lc_messages_dir, exist_ok=True)
                    with open(mo_path, "wb") as mo_file:
                        write_mo(mo_file, catalog)
        except Exception:
            # Fail silently to avoid breaking app if Babel tools unavailable
            pass

    _compile_translations_if_needed()

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
