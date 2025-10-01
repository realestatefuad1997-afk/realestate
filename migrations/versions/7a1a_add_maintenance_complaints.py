from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7a1a_add_maintenance_complaints'
down_revision = '6de2063996e2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'maintenance_requests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('contract_id', sa.Integer(), nullable=True),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('subject', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('priority', sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(['contract_id'], ['contracts.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['users.id'], ),
    )
    op.create_index('ix_maintenance_requests_contract_id', 'maintenance_requests', ['contract_id'])
    op.create_index('ix_maintenance_requests_tenant_id', 'maintenance_requests', ['tenant_id'])

    op.create_table(
        'complaints',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('contract_id', sa.Integer(), nullable=True),
        sa.Column('subject', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['contract_id'], ['contracts.id'], ),
    )
    op.create_index('ix_complaints_tenant_id', 'complaints', ['tenant_id'])
    op.create_index('ix_complaints_contract_id', 'complaints', ['contract_id'])


def downgrade() -> None:
    op.drop_index('ix_complaints_contract_id', table_name='complaints')
    op.drop_index('ix_complaints_tenant_id', table_name='complaints')
    op.drop_table('complaints')
    op.drop_index('ix_maintenance_requests_tenant_id', table_name='maintenance_requests')
    op.drop_index('ix_maintenance_requests_contract_id', table_name='maintenance_requests')
    op.drop_table('maintenance_requests')

