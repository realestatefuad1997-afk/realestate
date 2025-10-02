import os

# المسار الأساسي للمشروع
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = "supersecretkey"  # غيرها في الإنتاج
    # قاعدة بيانات SQLite داخل مجلد المشروع
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'site.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Upload settings (inside app/static/uploads)
    APP_DIR = os.path.join(BASE_DIR, 'app')
    UPLOAD_FOLDER = os.path.join(APP_DIR, 'static', 'uploads')
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB limit
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
