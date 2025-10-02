"""add apartments table

Revision ID: a3b8d6c1e9ab
Revises: 2bf1a9a0f9b4
Create Date: 2025-10-02 00:10:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a3b8d6c1e9ab'
down_revision = '2bf1a9a0f9b4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'apartments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('building_id', sa.Integer(), sa.ForeignKey('properties.id'), nullable=False, index=True),
        sa.Column('number', sa.String(length=50), nullable=True),
        sa.Column('floor', sa.Integer(), nullable=True),
        sa.Column('area_sqm', sa.Numeric(10, 2), nullable=True),
        sa.Column('bedrooms', sa.Integer(), nullable=True),
        sa.Column('bathrooms', sa.Integer(), nullable=True),
        sa.Column('rent_price', sa.Numeric(12, 2), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='available'),
        sa.Column('images', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_apartments_building_id', 'apartments', ['building_id'])


def downgrade() -> None:
    op.drop_index('ix_apartments_building_id', table_name='apartments')
    op.drop_table('apartments')
