from datetime import date, timedelta
import click
from flask import Flask
from .extensions import db
from .models import User, Property, Contract, Payment, Account, Company
from .tenant_manager import TenantManager
import subprocess
import sys


def register_cli(app: Flask) -> None:
    @app.cli.command("compile-translations")
    def compile_translations():
        try:
            subprocess.check_call([sys.executable, "-m", "babel.messages.frontend", "compile_catalog", "-d", "app/translations"])  # type: ignore
        except Exception:
            subprocess.check_call(["pybabel", "compile", "-d", "app/translations"])  # type: ignore
    @app.cli.command("create-admin")
    @click.option("--username", prompt=True)
    @click.option("--email", prompt=True)
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    def create_admin(username: str, email: str, password: str):
        if User.query.filter((User.username == username) | (User.email == email)).first():
            click.echo("User with same username or email already exists")
            return
        user = User(username=username, email=email, role="admin")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo("Admin created")

    @app.cli.command("seed-data")
    def seed_data():
        # Basic roles users
        if not User.query.filter_by(username="employee").first():
            u = User(username="employee", email="employee@example.com", role="employee")
            u.set_password("password")
            db.session.add(u)
        if not User.query.filter_by(username="tenant").first():
            t = User(username="tenant", email="tenant@example.com", role="tenant")
            t.set_password("password")
            db.session.add(t)
        if not User.query.filter_by(username="accountant").first():
            a = User(username="accountant", email="accountant@example.com", role="accountant")
            a.set_password("password")
            db.session.add(a)

        # Properties
        if Property.query.count() == 0:
            p1 = Property(title="Apartment A", description="Sea view", price=800.00, status="available")
            p2 = Property(title="Villa B", description="Garden", price=2500.00, status="available")
            db.session.add_all([p1, p2])
            db.session.flush()

        db.session.commit()

        # Seed minimal chart of accounts
        def _get_or_create_account(code: str, name: str, acc_type: str) -> Account:
            acc = Account.query.filter_by(code=code).first()
            if not acc:
                acc = Account(code=code, name=name, type=acc_type)
                db.session.add(acc)
                db.session.commit()
            return acc

        _get_or_create_account("1000", "Cash", "asset")
        _get_or_create_account("1100", "Accounts Receivable", "asset")
        _get_or_create_account("4000", "Rental Income", "income")
        _get_or_create_account("5000", "General Expenses", "expense")

        # Contracts and payments
        tenant = User.query.filter_by(role="tenant").first()
        prop = Property.query.first()
        if tenant and prop and not Contract.query.first():
            contract = Contract(
                property_id=prop.id,
                tenant_id=tenant.id,
                start_date=date.today(),
                end_date=date.today() + timedelta(days=365),
                rent_amount=prop.price,
                status="active",
            )
            db.session.add(contract)
            db.session.flush()
            for i in range(1, 4):
                payment = Payment(
                    contract_id=contract.id,
                    amount=prop.price,
                    due_date=date.today() + timedelta(days=30 * i),
                    status="unpaid",
                )
                db.session.add(payment)
            db.session.commit()
        click.echo("Seed data inserted")

    @app.cli.command("tenant-seed")
    @click.option("--subdomain", required=True)
    def tenant_seed(subdomain: str):
        c = Company.query.filter_by(subdomain=subdomain).first()
        if not c:
            click.echo("Company not found")
            return
        from sqlalchemy import create_engine
        engine = create_engine(c.db_uri, pool_pre_ping=True)
        engines = db.engines  # type: ignore[attr-defined]
        prev = engines.get(None)
        engines[None] = engine
        try:
            # Reuse seed logic inline
            if not User.query.filter_by(username="employee").first():
                u = User(username="employee", email="employee@example.com", role="employee")
                u.set_password("password")
                db.session.add(u)
            if not User.query.filter_by(username="tenant").first():
                t = User(username="tenant", email="tenant@example.com", role="tenant")
                t.set_password("password")
                db.session.add(t)
            if not User.query.filter_by(username="accountant").first():
                a = User(username="accountant", email="accountant@example.com", role="accountant")
                a.set_password("password")
                db.session.add(a)
            if Property.query.count() == 0:
                p1 = Property(title="Apartment A", description="Sea view", price=800.00, status="available")
                p2 = Property(title="Villa B", description="Garden", price=2500.00, status="available")
                db.session.add_all([p1, p2])
                db.session.flush()
            db.session.commit()
            def _get_or_create_account(code: str, name: str, acc_type: str) -> Account:
                acc = Account.query.filter_by(code=code).first()
                if not acc:
                    acc = Account(code=code, name=name, type=acc_type)
                    db.session.add(acc)
                    db.session.commit()
                return acc
            _get_or_create_account("1000", "Cash", "asset")
            _get_or_create_account("1100", "Accounts Receivable", "asset")
            _get_or_create_account("4000", "Rental Income", "income")
            _get_or_create_account("5000", "General Expenses", "expense")
            tenant = User.query.filter_by(role="tenant").first()
            prop = Property.query.first()
            if tenant and prop and not Contract.query.first():
                contract = Contract(
                    property_id=prop.id,
                    tenant_id=tenant.id,
                    start_date=date.today(),
                    end_date=date.today() + timedelta(days=365),
                    rent_amount=prop.price,
                    status="active",
                )
                db.session.add(contract)
                db.session.flush()
                for i in range(1, 4):
                    payment = Payment(
                        contract_id=contract.id,
                        amount=prop.price,
                        due_date=date.today() + timedelta(days=30 * i),
                        status="unpaid",
                    )
                    db.session.add(payment)
                db.session.commit()
            click.echo(f"Seed data inserted for {subdomain}")
        finally:
            if prev is not None:
                engines[None] = prev
    # --- Tenancy CLI commands ---
    @app.cli.command("tenant-create")
    @click.option("--name", required=True, help="Company display name")
    @click.option("--subdomain", required=True, help="Unique company subdomain key")
    @click.option("--db-uri", default=None, help="Optional DB URI; default: per-company SQLite")
    def tenant_create(name: str, subdomain: str, db_uri: str | None):
        tm = TenantManager()
        spec = tm.build_sqlite_uri(subdomain) if not db_uri else None
        uri = db_uri or (spec.uri if spec else None)
        if uri is None:
            click.echo("Failed to build DB URI")
            return
        # Create master record
        c = Company(name=name, subdomain=subdomain, db_uri=uri)
        db_master.session.add(c)
        db_master.session.commit()
        # Ensure DB exists and create schema
        from sqlalchemy import create_engine
        engine = create_engine(uri, pool_pre_ping=True)
        engines = db.engines  # type: ignore[attr-defined]
        prev = engines.get(None)
        engines[None] = engine
        try:
            db.create_all()
        finally:
            if prev is not None:
                engines[None] = prev
        click.echo(f"Tenant '{name}' created at {uri}")

    @app.cli.command("tenant-export")
    @click.option("--subdomain", required=True)
    @click.option("--out", required=True, help="Output file path")
    def tenant_export(subdomain: str, out: str):
        c = Company.query.filter_by(subdomain=subdomain).first()
        if not c:
            click.echo("Company not found")
            return
        tm = TenantManager()
        if c.db_uri.startswith("sqlite"):
            tm.export_sqlite(c.db_uri, out)
            click.echo(f"Exported to {out}")
        else:
            click.echo("Use database-native tools to export non-SQLite DBs")

    @app.cli.command("tenant-delete")
    @click.option("--subdomain", required=True)
    def tenant_delete(subdomain: str):
        c = Company.query.filter_by(subdomain=subdomain).first()
        if not c:
            click.echo("Company not found")
            return
        uri = c.db_uri
        db_master.session.delete(c)
        db_master.session.commit()
        tm = TenantManager()
        if uri.startswith("sqlite"):
            tm.delete_sqlite(uri)
            click.echo("Company and SQLite DB removed")
        else:
            click.echo("Company removed. Drop the external DB manually.")

