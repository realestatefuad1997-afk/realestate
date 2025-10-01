import os

# المسار الأساسي للمشروع
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = "supersecretkey"  # غيرها في الإنتاج
    # قاعدة بيانات SQLite داخل مجلد المشروع
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'site.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
