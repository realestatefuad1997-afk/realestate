"""add building fields to properties

Revision ID: 2bf1a9a0f9b4
Revises: 
Create Date: 2025-10-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '2bf1a9a0f9b4'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:\n    op.add_column('properties', sa.Column('num_apartments', sa.Integer(), nullable=True))
    op.add_column('properties', sa.Column('num_floors', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('properties', 'num_floors')
    op.drop_column('properties', 'num_apartments')
