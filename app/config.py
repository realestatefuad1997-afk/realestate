import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    # مفتاح سري للتطبيق
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")

    # قاعدة البيانات SQLite
    # على ويندوز، استخدم ثلاثة / بعد sqlite:
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(basedir, 'instance', 'app.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # مجلد رفع الملفات
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", os.path.join(basedir, "uploads"))
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # 25 MB

    # اللغات المدعومة
    LANGUAGES = {"en": "English", "ar": "العربية"}
    BABEL_DEFAULT_LOCALE = "en"
    BABEL_DEFAULT_TIMEZONE = "UTC"

    # إعدادات إضافية يمكن تعديلها لاحقًا
    DEBUG = True
    TESTING = False
