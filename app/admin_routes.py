from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt

from . import db
from .models import (
	Property,
	Tenant,
	Employee,
	Transaction,
	Contract,
	Payment,
	get_or_create_property,
	get_or_create_tenant,
	get_or_create_employee,
	get_or_create_transaction,
)

admin_bp = Blueprint("admin", __name__)


# --- Helpers ---

def require_admin() -> Optional[Tuple[Dict[str, Any], int]]:
	claims = get_jwt()
	role = (claims or {}).get("role")
	if role != "admin":
		return {"status": "error", "message": "Admin access required"}, 403
	return None


def parse_sort_params(default_sort: str = "id", allowed: Optional[List[str]] = None) -> Tuple[str, bool]:
	sort_by = request.args.get("sort_by", default_sort)
	order = request.args.get("order", "asc").lower()
	if allowed and sort_by not in allowed:
		sort_by = default_sort
	desc = order == "desc"
	return sort_by, desc


def parse_date(value: Optional[str]) -> Optional[date]:
	if not value:
		return None
	try:
		return datetime.strptime(value, "%Y-%m-%d").date()
	except Exception:
		return None


# --- Dashboard ---

@admin_bp.get("/dashboard")
@jwt_required()
def admin_dashboard():
	guard = require_admin()
	if guard:
		return guard

	# Optional filters for transactions by date range and status
	start_date = parse_date(request.args.get("start_date"))
	end_date = parse_date(request.args.get("end_date"))
	txn_status = request.args.get("transaction_status")

	# Properties
	properties_q = Property.query
	sort_by, desc = parse_sort_params("created_at", ["created_at", "status", "property_type", "address"]) 
	sort_col = getattr(Property, sort_by)
	properties_q = properties_q.order_by(sort_col.desc() if desc else sort_col.asc())
	properties: List[Property] = properties_q.all()

	# Ensure referenced tenants exist for properties
	for prop in properties:
		if prop.tenant_id and not prop.tenant:
			tenant = get_or_create_tenant(email=f"unknown-{prop.tenant_id}@example.com", full_name="Unknown Tenant")
			prop.tenant = tenant

	# Tenants with contracts and payments
	tenants: List[Tenant] = Tenant.query.order_by(Tenant.created_at.desc()).all()

	# Employees with tasks
	employees: List[Employee] = Employee.query.order_by(Employee.created_at.desc()).all()

	# Transactions with filters
	txn_q = Transaction.query
	if start_date:
		txn_q = txn_q.filter(Transaction.date >= start_date)
	if end_date:
		txn_q = txn_q.filter(Transaction.date <= end_date)
	if txn_status:
		txn_q = txn_q.filter(Transaction.status == txn_status)
	txn_sort_by, txn_desc = parse_sort_params("date", ["date", "amount", "status", "created_at"])
	txn_sort_col = getattr(Transaction, txn_sort_by)
	transactions: List[Transaction] = txn_q.order_by(txn_sort_col.desc() if txn_desc else txn_sort_col.asc()).all()

	# Ensure referenced tenant/property exist for transactions
	for tx in transactions:
		if tx.tenant_id and not tx.tenant:
			tx.tenant = get_or_create_tenant(email=f"unknown-{tx.tenant_id}@example.com", full_name="Unknown Tenant")
		if tx.property_id and not tx.property:
			tx.property = get_or_create_property(address=f"Unknown Address #{tx.property_id}")

	db.session.commit()

	# Serialize
	def serialize_property(p: Property) -> Dict[str, Any]:
		return {
			"id": p.id,
			"address": p.address,
			"status": p.status,
			"type": p.property_type,
			"tenant": (
				{
					"id": p.tenant.id,
					"full_name": p.tenant.full_name,
					"email": p.tenant.email,
				}
				if p.tenant
				else None
			),
			"created_at": p.created_at.isoformat(),
			"updated_at": p.updated_at.isoformat(),
		}

	def serialize_contract(c: Contract) -> Dict[str, Any]:
		return {
			"id": c.id,
			"property_id": c.property_id,
			"start_date": c.start_date.isoformat(),
			"end_date": c.end_date.isoformat() if c.end_date else None,
			"terms": c.terms,
		}

	def serialize_payment(pm: Payment) -> Dict[str, Any]:
		return {
			"id": pm.id,
			"amount": float(pm.amount),
			"status": pm.status,
			"paid_at": pm.paid_at.isoformat(),
			"note": pm.note,
		}

	def serialize_tenant(t: Tenant) -> Dict[str, Any]:
		return {
			"id": t.id,
			"full_name": t.full_name,
			"email": t.email,
			"phone": t.phone,
			"contracts": [serialize_contract(c) for c in t.contracts],
			"payments": [serialize_payment(pm) for pm in t.payments],
			"created_at": t.created_at.isoformat(),
			"updated_at": t.updated_at.isoformat(),
		}

	def serialize_employee(e: Employee) -> Dict[str, Any]:
		return {
			"id": e.id,
			"full_name": e.full_name,
			"email": e.email,
			"role": e.role,
			"completed_tasks": sum(1 for t in e.tasks if t.completed),
			"tasks": [
				{
					"id": t.id,
					"description": t.description,
					"completed": t.completed,
					"completed_at": t.completed_at.isoformat() if t.completed_at else None,
				}
				for t in e.tasks
			],
			"created_at": e.created_at.isoformat(),
			"updated_at": e.updated_at.isoformat(),
		}

	def serialize_transaction(tx: Transaction) -> Dict[str, Any]:
		return {
			"id": tx.id,
			"status": tx.status,
			"amount": float(tx.amount),
			"date": tx.date.isoformat(),
			"reference_code": tx.reference_code,
			"tenant": (
				{"id": tx.tenant.id, "full_name": tx.tenant.full_name, "email": tx.tenant.email}
				if tx.tenant
				else None
			),
			"property": (
				{"id": tx.property.id, "address": tx.property.address}
				if tx.property
				else None
			),
			"created_at": tx.created_at.isoformat(),
			"updated_at": tx.updated_at.isoformat(),
		}

	response = {
		"status": "ok",
		"data": {
			"properties": [serialize_property(p) for p in properties],
			"tenants": [serialize_tenant(t) for t in tenants],
			"employees": [serialize_employee(e) for e in employees],
			"transactions": [serialize_transaction(tx) for tx in transactions],
		},
	}

	return response, 200


# --- Create-if-not-exists Endpoints ---

@admin_bp.post("/properties")
@jwt_required()
def create_property():
	guard = require_admin()
	if guard:
		return guard

	data = request.get_json(silent=True) or {}
	address = (data.get("address") or "").strip()
	if not address:
		return {"status": "error", "message": "address is required"}, 400
	status_value = (data.get("status") or "available").strip()
	prop_type = (data.get("type") or data.get("property_type") or "residential").strip()
	tenant_email = (data.get("tenant_email") or data.get("tenantEmail") or None)

	prop = get_or_create_property(address=address, status=status_value, property_type=prop_type, tenant_email=tenant_email)
	db.session.commit()

	sort_by, desc = parse_sort_params("created_at", ["created_at", "status", "property_type", "address"]) 
	list_all = request.args.get("return_all") == "true"
	if list_all:
		q = Property.query
		sort_col = getattr(Property, sort_by)
		q = q.order_by(sort_col.desc() if desc else sort_col.asc())
		items = q.all()
		return {
			"status": "ok",
			"message": "created or fetched",
			"item": {"id": prop.id, "address": prop.address},
			"items": [
				{"id": p.id, "address": p.address, "status": p.status, "type": p.property_type}
				for p in items
			],
		}, 200

	return {"status": "ok", "message": "created or fetched", "id": prop.id, "address": prop.address}, 200


@admin_bp.post("/tenants")
@jwt_required()
def create_tenant():
	guard = require_admin()
	if guard:
		return guard

	data = request.get_json(silent=True) or {}
	email = (data.get("email") or "").strip().lower()
	full_name = (data.get("full_name") or data.get("name") or "").strip() or "Unknown Tenant"
	phone = (data.get("phone") or None)
	if not email:
		return {"status": "error", "message": "email is required"}, 400

	tenant = get_or_create_tenant(email=email, full_name=full_name, phone=phone)

	# Optionally create contract
	contract_data = data.get("contract") or {}
	if contract_data:
		start_date_str = contract_data.get("start_date")
		start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date() if start_date_str else date.today()
		end_date_str = contract_data.get("end_date")
		end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date() if end_date_str else None
		property_address = contract_data.get("property_address")
		prop = get_or_create_property(property_address) if property_address else None
		contract = Contract(tenant=tenant, property=prop, start_date=start_date, end_date=end_date, terms=contract_data.get("terms"))
		db.session.add(contract)

	# Optionally create a payment
	payment_data = data.get("payment") or {}
	if payment_data:
		amount = float(payment_data.get("amount"))
		status_value = (payment_data.get("status") or "completed").strip()
		paid_at_str = payment_data.get("paid_at")
		paid_at = datetime.fromisoformat(paid_at_str) if paid_at_str else datetime.utcnow()
		payment = Payment(tenant=tenant, amount=amount, status=status_value, paid_at=paid_at, note=payment_data.get("note"))
		db.session.add(payment)

	db.session.commit()

	sort_by, desc = parse_sort_params("created_at", ["created_at", "full_name", "email"]) 
	list_all = request.args.get("return_all") == "true"
	if list_all:
		q = Tenant.query
		sort_col = getattr(Tenant, sort_by)
		q = q.order_by(sort_col.desc() if desc else sort_col.asc())
		items = q.all()
		return {
			"status": "ok",
			"message": "created or fetched",
			"item": {"id": tenant.id, "email": tenant.email},
			"items": [
				{"id": t.id, "email": t.email, "full_name": t.full_name}
				for t in items
			],
		}, 200

	return {"status": "ok", "message": "created or fetched", "id": tenant.id, "email": tenant.email}, 200


@admin_bp.post("/employees")
@jwt_required()
def create_employee():
	guard = require_admin()
	if guard:
		return guard

	data = request.get_json(silent=True) or {}
	email = (data.get("email") or "").strip().lower()
	full_name = (data.get("full_name") or data.get("name") or "").strip() or "Unknown Employee"
	role = (data.get("role") or "staff").strip()
	if not email:
		return {"status": "error", "message": "email is required"}, 400

	employee = get_or_create_employee(email=email, full_name=full_name, role=role)

	# Optionally create tasks
	from .models import Task
	tasks_data = data.get("tasks") or []
	for t in tasks_data:
		desc = (t.get("description") or "").strip()
		if not desc:
			continue
		completed = bool(t.get("completed", False))
		completed_at = datetime.fromisoformat(t["completed_at"]) if t.get("completed_at") else None
		task = Task(employee=employee, description=desc, completed=completed, completed_at=completed_at)
		db.session.add(task)

	db.session.commit()

	sort_by, desc = parse_sort_params("created_at", ["created_at", "full_name", "email", "role"]) 
	list_all = request.args.get("return_all") == "true"
	if list_all:
		q = Employee.query
		sort_col = getattr(Employee, sort_by)
		q = q.order_by(sort_col.desc() if desc else sort_col.asc())
		items = q.all()
		return {
			"status": "ok",
			"message": "created or fetched",
			"item": {"id": employee.id, "email": employee.email},
			"items": [
				{"id": e.id, "email": e.email, "full_name": e.full_name, "role": e.role}
				for e in items
			],
		}, 200

	return {"status": "ok", "message": "created or fetched", "id": employee.id, "email": employee.email}, 200


@admin_bp.post("/transactions")
@jwt_required()
def create_transaction():
	guard = require_admin()
	if guard:
		return guard

	data = request.get_json(silent=True) or {}
	reference_code = (data.get("reference_code") or data.get("reference") or None)
	try:
		amount = float(data.get("amount"))
	except Exception:
		return {"status": "error", "message": "amount is required and must be numeric"}, 400
	status_value = (data.get("status") or "pending").strip()
	date_str = data.get("date")
	date_value = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()
	tenant_email = data.get("tenant_email")
	property_address = data.get("property_address")

	txn = get_or_create_transaction(reference_code=reference_code, amount=amount, status=status_value, date_value=date_value, tenant_email=tenant_email, property_address=property_address)
	db.session.commit()

	# Optional filter/sort return
	list_all = request.args.get("return_all") == "true"
	txn_sort_by, txn_desc = parse_sort_params("date", ["date", "amount", "status", "created_at"])
	if list_all:
		q = Transaction.query
		start_date = parse_date(request.args.get("start_date"))
		end_date = parse_date(request.args.get("end_date"))
		if start_date:
			q = q.filter(Transaction.date >= start_date)
		if end_date:
			q = q.filter(Transaction.date <= end_date)
		if request.args.get("status"):
			q = q.filter(Transaction.status == request.args.get("status"))
		sort_col = getattr(Transaction, txn_sort_by)
		q = q.order_by(sort_col.desc() if txn_desc else sort_col.asc())
		items = q.all()
		return {
			"status": "ok",
			"message": "created or fetched",
			"item": {"id": txn.id, "reference_code": txn.reference_code},
			"items": [
				{"id": t.id, "reference_code": t.reference_code, "status": t.status, "amount": float(t.amount)}
				for t in items
			],
		}, 200

	return {
		"status": "ok",
		"message": "created or fetched",
		"id": txn.id,
		"reference_code": txn.reference_code,
	}, 200