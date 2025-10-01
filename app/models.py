from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from flask import current_app
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import UniqueConstraint, func, Index
from . import db


class TimestampMixin:
	created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
	updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class User(db.Model, TimestampMixin):
	__tablename__ = "users"

	id = db.Column(db.Integer, primary_key=True)
	email = db.Column(db.String(255), unique=True, nullable=False, index=True)
	password_hash = db.Column(db.String(255), nullable=False)
	role = db.Column(db.String(50), nullable=False, default="viewer")
	full_name = db.Column(db.String(255), nullable=True)

	def set_password(self, password: str) -> None:
		self.password_hash = generate_password_hash(password)

	def check_password(self, password: str) -> bool:
		return check_password_hash(self.password_hash, password)


class Tenant(db.Model, TimestampMixin):
	__tablename__ = "tenants"
	id = db.Column(db.Integer, primary_key=True)
	full_name = db.Column(db.String(255), nullable=False)
	email = db.Column(db.String(255), unique=True, nullable=False, index=True)
	phone = db.Column(db.String(50), nullable=True)

	contracts = db.relationship("Contract", backref="tenant", lazy=True, cascade="all, delete-orphan")
	payments = db.relationship("Payment", backref="tenant", lazy=True, cascade="all, delete-orphan")


class Property(db.Model, TimestampMixin):
	__tablename__ = "properties"
	id = db.Column(db.Integer, primary_key=True)
	address = db.Column(db.String(255), unique=True, nullable=False, index=True)
	status = db.Column(db.String(50), nullable=False, default="available")  # available, occupied, maintenance
	property_type = db.Column(db.String(50), nullable=False, default="residential")  # residential, commercial

	tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=True)
	tenant = db.relationship("Tenant", backref="properties", lazy=True)


class Contract(db.Model, TimestampMixin):
	__tablename__ = "contracts"
	id = db.Column(db.Integer, primary_key=True)
	tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False)
	property_id = db.Column(db.Integer, db.ForeignKey("properties.id"), nullable=True)
	start_date = db.Column(db.Date, nullable=False)
	end_date = db.Column(db.Date, nullable=True)
	terms = db.Column(db.Text, nullable=True)

	property = db.relationship("Property", backref="contracts", lazy=True)


class Payment(db.Model, TimestampMixin):
	__tablename__ = "payments"
	id = db.Column(db.Integer, primary_key=True)
	tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False)
	amount = db.Column(db.Numeric(12, 2), nullable=False)
	status = db.Column(db.String(50), nullable=False, default="completed")  # pending, completed, failed
	paid_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
	note = db.Column(db.String(255), nullable=True)

	Index("idx_payments_tenant_paidat", tenant_id, paid_at)


class Employee(db.Model, TimestampMixin):
	__tablename__ = "employees"
	id = db.Column(db.Integer, primary_key=True)
	full_name = db.Column(db.String(255), nullable=False)
	email = db.Column(db.String(255), unique=True, nullable=False, index=True)
	role = db.Column(db.String(50), nullable=False, default="staff")  # admin, staff, manager

	tasks = db.relationship("Task", backref="employee", lazy=True, cascade="all, delete-orphan")


class Task(db.Model, TimestampMixin):
	__tablename__ = "tasks"
	id = db.Column(db.Integer, primary_key=True)
	employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
	description = db.Column(db.String(255), nullable=False)
	completed = db.Column(db.Boolean, default=False, nullable=False)
	completed_at = db.Column(db.DateTime, nullable=True)


class Transaction(db.Model, TimestampMixin):
	__tablename__ = "transactions"
	id = db.Column(db.Integer, primary_key=True)
	status = db.Column(db.String(50), nullable=False, default="pending")  # pending, settled, failed
	amount = db.Column(db.Numeric(12, 2), nullable=False)
	date = db.Column(db.Date, nullable=False, default=func.current_date())
	reference_code = db.Column(db.String(100), nullable=True)

	tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=True)
	property_id = db.Column(db.Integer, db.ForeignKey("properties.id"), nullable=True)

	tenant = db.relationship("Tenant", backref="transactions", lazy=True)
	property = db.relationship("Property", backref="transactions", lazy=True)

	__table_args__ = (
		UniqueConstraint("reference_code", name="uq_transactions_reference_code"),
	)


# Utility: get-or-create helpers to avoid duplication

def get_or_create_tenant(email: str, full_name: Optional[str] = None, phone: Optional[str] = None) -> Tenant:
	tenant: Optional[Tenant] = Tenant.query.filter_by(email=email).first()
	if tenant:
		return tenant
	tenant = Tenant(email=email, full_name=full_name or "Unknown Tenant", phone=phone)
	db.session.add(tenant)
	db.session.flush()
	return tenant


def get_or_create_employee(email: str, full_name: Optional[str] = None, role: Optional[str] = None) -> Employee:
	employee: Optional[Employee] = Employee.query.filter_by(email=email).first()
	if employee:
		return employee
	employee = Employee(email=email, full_name=full_name or "Unknown Employee", role=role or "staff")
	db.session.add(employee)
	db.session.flush()
	return employee


def get_or_create_property(address: str, status: Optional[str] = None, property_type: Optional[str] = None, tenant_email: Optional[str] = None) -> Property:
	prop: Optional[Property] = Property.query.filter_by(address=address).first()
	if prop:
		return prop
	tenant = None
	if tenant_email:
		tenant = get_or_create_tenant(email=tenant_email)
	prop = Property(address=address, status=status or "available", property_type=property_type or "residential", tenant=tenant)
	db.session.add(prop)
	db.session.flush()
	return prop


def get_or_create_transaction(reference_code: Optional[str], amount: float, status: str = "pending", date_value: Optional[date] = None, tenant_email: Optional[str] = None, property_address: Optional[str] = None) -> Transaction:
	txn: Optional[Transaction] = None
	if reference_code:
		txn = Transaction.query.filter_by(reference_code=reference_code).first()
	if txn:
		return txn
	tenant = get_or_create_tenant(tenant_email) if tenant_email else None
	prop = get_or_create_property(property_address) if property_address else None
	txn = Transaction(reference_code=reference_code, amount=amount, status=status, date=date_value or datetime.utcnow().date(), tenant=tenant, property=prop)
	db.session.add(txn)
	db.session.flush()
	return txn


def seed_admin_user() -> None:
	from os import getenv
	admin_email = getenv("ADMIN_EMAIL", "admin@example.com")
	admin_password = getenv("ADMIN_PASSWORD", "ChangeThisAdminPassword123!")

	existing = User.query.filter_by(email=admin_email).first()
	if existing:
		return
	admin = User(email=admin_email, role="admin", full_name="System Admin")
	admin.set_password(admin_password)
	db.session.add(admin)
	db.session.commit()
	current_app.logger.info("Seeded default admin user: %s", admin_email)
