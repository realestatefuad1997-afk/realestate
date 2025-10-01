"""ensure maintenance_requests and complaints exist

Revision ID: 20251001_ensure_mc
Revises: 6de2063996e2
Create Date: 2025-10-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = '20251001_ensure_mc'
down_revision = '6de2063996e2'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)

    tables = set(inspector.get_table_names())

    if 'maintenance_requests' not in tables:
        op.create_table(
            'maintenance_requests',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('tenant_id', sa.Integer(), nullable=False),
            sa.Column('property_id', sa.Integer(), nullable=True),
            sa.Column('title', sa.String(length=200), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('status', sa.String(length=50), nullable=False),
            sa.Column('employee_notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['tenant_id'], ['users.id']),
            sa.ForeignKeyConstraint(['property_id'], ['properties.id']),
            sa.PrimaryKeyConstraint('id'),
        )
    else:
        # ensure employee_notes exists
        cols = {c['name'] for c in inspector.get_columns('maintenance_requests')}
        if 'employee_notes' not in cols:
            with op.batch_alter_table('maintenance_requests') as batch_op:
                batch_op.add_column(sa.Column('employee_notes', sa.Text(), nullable=True))

    if 'complaints' not in tables:
        op.create_table(
            'complaints',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('tenant_id', sa.Integer(), nullable=False),
            sa.Column('subject', sa.String(length=200), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('status', sa.String(length=50), nullable=False),
            sa.Column('employee_notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['tenant_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id'),
        )
    else:
        cols = {c['name'] for c in inspector.get_columns('complaints')}
        if 'employee_notes' not in cols:
            with op.batch_alter_table('complaints') as batch_op:
                batch_op.add_column(sa.Column('employee_notes', sa.Text(), nullable=True))


def downgrade():
    # This migration is idempotent and only ensures presence; downgrading would drop newly created tables
    op.drop_table('complaints')
    op.drop_table('maintenance_requests')

