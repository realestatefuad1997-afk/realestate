from app import create_app, db
from app.models import seed_admin_user

app = create_app()

# Ensure tables exist and seed admin on first run
with app.app_context():
	db.create_all()
	seed_admin_user()

if __name__ == "__main__":
	app.run(host="0.0.0.0", port=8000)
