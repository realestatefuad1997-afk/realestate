"""add notes to maintenance and complaints

Revision ID: b9e277e8a01b
Revises: 6de2063996e2
Create Date: 2025-10-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b9e277e8a01b'
down_revision = '6de2063996e2'
branch_labels = None
depends_on = None


def upgrade():
    # Add notes columns if tables exist
    with op.batch_alter_table('maintenance_requests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('notes', sa.Text(), nullable=True))
    with op.batch_alter_table('complaints', schema=None) as batch_op:
        batch_op.add_column(sa.Column('notes', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('complaints', schema=None) as batch_op:
        batch_op.drop_column('notes')
    with op.batch_alter_table('maintenance_requests', schema=None) as batch_op:
        batch_op.drop_column('notes')
