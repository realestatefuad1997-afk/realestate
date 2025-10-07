from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker

# بيانات الاتصال بقاعدة PostgreSQL
DATABASE_URL = "postgresql://realestate_g8it_user:7cBCDJOvKnO7et2yn8tBtDGzoo6cprW5@dpg-d3hupr33fgac73a4j1tg-a.oregon-postgres.render.com/realestate_g8it"

engine = create_engine(DATABASE_URL)
Base = declarative_base()

# نموذج جدول المستخدمين
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(255), nullable=False)  # خزنها مشفرة (هاش)
    is_superadmin = Column(Boolean, default=False)

# إنشاء الجداول في القاعدة
Base.metadata.create_all(engine)

# إعداد جلسة عمل
Session = sessionmaker(bind=engine)
session = Session()

# إنشاء سوبر أدمين جديد
def create_superadmin(username, password):
    # هنا لازم تشفر الباسورد قبل التخزين (مثل bcrypt)
    hashed_password = password  # استبدل هذا بالتشفير المناسب
    superadmin = User(username=username, password=hashed_password, is_superadmin=True)
    session.add(superadmin)
    session.commit()
    print(f"تم إنشاء السوبر أدمين: {username}")

# مثال: إنشاء سوبر أدمين جديد
create_superadmin("admin", "your_secure_password")
