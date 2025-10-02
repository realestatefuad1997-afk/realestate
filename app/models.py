from datetime import datetime, date
from typing import Optional
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from .extensions import db


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class User(UserMixin, db.Model, TimestampMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(32), nullable=False, index=True)

    contracts = db.relationship("Contract", back_populates="tenant", lazy="dynamic")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_employee(self) -> bool:
        return self.role == "employee"

    @property
    def is_tenant(self) -> bool:
        return self.role == "tenant"

    @property
    def is_accountant(self) -> bool:
        return self.role == "accountant"


class Property(db.Model, TimestampMixin):
    __tablename__ = "properties"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    status = db.Column(db.String(50), nullable=False, default="available")
    images = db.Column(db.Text)  # store comma-separated file names or JSON

    contracts = db.relationship("Contract", back_populates="property", lazy="dynamic")


class Contract(db.Model, TimestampMixin):
    __tablename__ = "contracts"

    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey("properties.id"), nullable=False, index=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    rent_amount = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(db.String(50), nullable=False, default="active")
    document_path = db.Column(db.String(500))

    property = db.relationship("Property", back_populates="contracts")
    tenant = db.relationship("User", back_populates="contracts")
    payments = db.relationship("Payment", back_populates="contract", lazy="dynamic")


class Payment(db.Model, TimestampMixin):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    contract_id = db.Column(db.Integer, db.ForeignKey("contracts.id"), nullable=False, index=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    paid_date = db.Column(db.Date)
    method = db.Column(db.String(50))  # cash, card, transfer
    status = db.Column(db.String(50), nullable=False, default="unpaid")

    contract = db.relationship("Contract", back_populates="payments")
    invoice = db.relationship("Invoice", back_populates="payment", uselist=False)


class Invoice(db.Model, TimestampMixin):
    __tablename__ = "invoices"

    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey("payments.id"), nullable=False, unique=True)
    file_path = db.Column(db.String(500), nullable=False)

    payment = db.relationship("Payment", back_populates="invoice")


# --- Service and Support domain ---


class MaintenanceRequest(db.Model, TimestampMixin):
    __tablename__ = "maintenance_requests"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    property_id = db.Column(db.Integer, db.ForeignKey("properties.id"), nullable=True, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), nullable=False, default="new")  # new, in_progress, resolved, closed
    notes = db.Column(db.Text)


class Complaint(db.Model, TimestampMixin):
    __tablename__ = "complaints"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    subject = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), nullable=False, default="new")  # new, reviewing, resolved, closed
    notes = db.Column(db.Text)
