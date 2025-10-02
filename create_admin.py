# create_admin.py
import getpass
from app import create_app, db
from app.models import User
from werkzeug.security import generate_password_hash

app = create_app()

ADMIN_USERNAME = "admin"
ADMIN_EMAIL = "admin@example.com"

with app.app_context():
    existing_admin = User.query.filter_by(username=ADMIN_USERNAME).first()
    if existing_admin:
        print(f"Admin '{ADMIN_USERNAME}' موجود مسبقًا.")
    else:
        pwd = getpass.getpass("ادخل كلمة مرور المدير (لن تظهر أثناء الكتابة): ")
        if not pwd:
            print("لم تدخل كلمة مرور — تم الإلغاء.")
        else:
            admin_user = User(
                username=ADMIN_USERNAME,
                email=ADMIN_EMAIL,
                password_hash=generate_password_hash(pwd),  # استخدم الحقل الصحيح
                role="admin"
            )
            db.session.add(admin_user)
            db.session.commit()
            print(f"تم إنشاء المدير '{ADMIN_USERNAME}' بنجاح.")
