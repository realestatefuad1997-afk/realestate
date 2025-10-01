from flask import Blueprint, request
from flask_jwt_extended import create_access_token
from .models import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/login")
def login():
	data = request.get_json(silent=True) or {}
	email = (data.get("email") or "").strip().lower()
	password = data.get("password") or ""

	if not email or not password:
		return {"status": "error", "message": "Email and password are required."}, 400

	user = User.query.filter_by(email=email).first()
	if not user or not user.check_password(password):
		return {"status": "error", "message": "Invalid credentials."}, 401

	access_token = create_access_token(identity={"id": user.id, "role": user.role, "email": user.email})
	return {
		"status": "ok",
		"message": "Login successful",
		"access_token": access_token,
		"user": {"id": user.id, "email": user.email, "role": user.role, "full_name": user.full_name},
	}, 200