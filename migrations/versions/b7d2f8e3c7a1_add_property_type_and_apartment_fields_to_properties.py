"""add property_type and apartment fields to properties

Revision ID: b7d2f8e3c7a1
Revises: a3b8d6c1e9ab
Create Date: 2025-10-02 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b7d2f8e3c7a1'
down_revision = 'a3b8d6c1e9ab'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # property_type with default 'building' for existing rows
    op.add_column('properties', sa.Column('property_type', sa.String(length=20), nullable=False, server_default='building'))
    op.create_index('ix_properties_property_type', 'properties', ['property_type'])

    # Apartment-specific fields for standalone apartments
    op.add_column('properties', sa.Column('number', sa.String(length=50), nullable=True))
    op.add_column('properties', sa.Column('floor', sa.Integer(), nullable=True))
    op.add_column('properties', sa.Column('area_sqm', sa.Numeric(10, 2), nullable=True))
    op.add_column('properties', sa.Column('bedrooms', sa.Integer(), nullable=True))
    op.add_column('properties', sa.Column('bathrooms', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('properties', 'bathrooms')
    op.drop_column('properties', 'bedrooms')
    op.drop_column('properties', 'area_sqm')
    op.drop_column('properties', 'floor')
    op.drop_column('properties', 'number')
    op.drop_index('ix_properties_property_type', table_name='properties')
    op.drop_column('properties', 'property_type')
