from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20241001_0002'
down_revision = '20241001_0001'
branch_labels = None
depends_on = None

# Contract phase: remove old column, potentially unsafe but allowed in contract
PHASE = "contract"

def upgrade():
    # After application deploy and backfill, it's safe to remove legacy column
    with op.batch_alter_table('orders') as batch_op:
        batch_op.drop_column('legacy_status')


def downgrade():
    with op.batch_alter_table('orders') as batch_op:
        batch_op.add_column(sa.Column('legacy_status', sa.String(length=50), nullable=True))

