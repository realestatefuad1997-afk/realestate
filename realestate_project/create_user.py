# create_user.py
from app import create_app
from app.extensions import db
from app.models import User
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    username = "admin"
    email = "admin@example.com"
    password = "123"  # غيّرها لما تبي
    hashed = generate_password_hash(password)
    user = User(username=username, email=email, password=hashed)
    db.session.add(user)
    db.session.commit()
    print(f"Created user: {username} / {password}")
