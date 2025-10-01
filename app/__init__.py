import os
from datetime import timedelta
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()


def create_app() -> Flask:
	app = Flask(__name__)

	# Config
	app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///app.db")
	app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
	app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")
	app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret")
	app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=8)

	# Init extensions
	db.init_app(app)
	migrate.init_app(app, db)
	jwt.init_app(app)

	# Blueprints
	from .auth import auth_bp
	from .admin_routes import admin_bp

	app.register_blueprint(auth_bp, url_prefix="/auth")
	app.register_blueprint(admin_bp, url_prefix="/admin")

	@app.get("/health")
	def health_check():
		return {"status": "ok"}, 200

	return app
