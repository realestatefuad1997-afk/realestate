import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")

    # --- Databases ---
    # MASTER database holds Super Admin users and Companies registry
    MASTER_DATABASE_URI = os.getenv(
        "MASTER_DATABASE_URI",
        f"sqlite:///{os.path.join(basedir, 'instance', 'master.db')}",
    )
    # Default tenant database URI (used only for Alembic and when no company bound)
    # Keep legacy single-tenant sqlite as the default tenant engine when needed
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "TENANT_DEFAULT_DATABASE_URI",
        f"sqlite:///{os.path.join(basedir, 'instance', 'app.db')}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Directory where per-company SQLite databases will be stored by default
    COMPANY_DB_DIR = os.getenv("COMPANY_DB_DIR", os.path.join(os.path.dirname(__file__), "..", "companies"))

    # Base directory to store user uploads; served via /uploads/<filename>
    UPLOAD_FOLDER = os.getenv(
        "UPLOAD_FOLDER",
        os.path.join(os.path.dirname(__file__), 'uploads'),
    )
    # Allowed file types for generic uploads (e.g., contracts)
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
    # Strict allowed extensions for property/apartment images
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg'}
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # 25 MB

    # i18n
    LANGUAGES = {"en": "English", "ar": "العربية"}
    BABEL_DEFAULT_LOCALE = "en"
    BABEL_DEFAULT_TIMEZONE = "UTC"
