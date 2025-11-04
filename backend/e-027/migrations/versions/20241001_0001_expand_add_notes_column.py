from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20241001_0001'
down_revision = None
branch_labels = None
depends_on = None

# Expand phase: add nullable column, safe for zero-downtime
PHASE = "expand"

def upgrade():
    # Example: add a nullable column which is safe
    op.add_column('orders', sa.Column('notes', sa.Text(), nullable=True))
    # Example: create an index concurrently for large table (PostgreSQL)
    op.create_index('ix_orders_created_at', 'orders', ['created_at'], postgresql_concurrently=True)


def downgrade():
    op.drop_index('ix_orders_created_at', table_name='orders', postgresql_concurrently=True)
    op.drop_column('orders', 'notes')

