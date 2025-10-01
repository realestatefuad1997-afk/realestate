## Admin Dashboard Backend (Flask)

A ready-to-run Flask backend for a real estate management Admin Dashboard.

### Features
- JWT authentication with admin-only access to `/admin/*` routes
- SQLAlchemy ORM models with timestamps
- Idempotent create-if-not-exists endpoints
- Dashboard aggregation across properties, tenants, employees, transactions
- Optional filtering and sorting parameters

### Quickstart
1. Create and activate a virtualenv, then install deps:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Configure environment:
```bash
cp .env.example .env
# Optionally edit DATABASE_URL, JWT_SECRET_KEY, ADMIN_EMAIL, ADMIN_PASSWORD
```

3. Run the server:
```bash
python run.py
# Server runs on http://0.0.0.0:8000
```

The first run will auto-create tables and seed an admin user using `ADMIN_EMAIL`/`ADMIN_PASSWORD`.

### Authentication
- Login: `POST /auth/login` with JSON `{ "email": "...", "password": "..." }`
- Use the returned JWT as a Bearer token for all `/admin/*` routes

### Admin Endpoints
- `GET /admin/dashboard?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&transaction_status=pending&sort_by=date&order=desc`
- `POST /admin/properties?return_all=true` body: `{ "address": "123 Main St", "status": "available", "type": "residential", "tenant_email": "t@example.com" }`
- `POST /admin/tenants?return_all=true` body: `{ "email": "t@example.com", "full_name": "Test Tenant", "contract": { "start_date": "2025-01-01", "property_address": "123 Main St" }, "payment": { "amount": 1200, "status": "completed" } }`
- `POST /admin/employees?return_all=true` body: `{ "email": "e@example.com", "full_name": "Emp Name", "role": "manager", "tasks": [{ "description": "Inspect APT", "completed": true }] }`
- `POST /admin/transactions?return_all=true&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&status=settled` body: `{ "reference_code": "INV-1001", "amount": 2500, "status": "settled", "date": "2025-09-01", "tenant_email": "t@example.com", "property_address": "123 Main St" }`

All POST endpoints are idempotent on their unique keys (`address`, `email`, `reference_code`) and will create missing related records when referenced, avoiding duplicates.

### Notes
- Default database is SQLite via `DATABASE_URL=sqlite:///app.db`. To use Postgres/MySQL, set the URL accordingly and install server dependencies.
- The code uses `Flask-Migrate` but also calls `db.create_all()` on startup for zero-setup. You can adopt migrations later.