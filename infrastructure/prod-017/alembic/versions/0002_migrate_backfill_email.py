from alembic import op
from alembic_helpers.backfill import backfill_in_batches
from alembic_helpers.zero_downtime import add_check_not_valid

# Revision identifiers, used by Alembic.
revision = "0002_migrate_backfill_email"
down_revision = "0001_expand_add_email_column"
branch_labels = None
depends_on = None
phase = "migrate"
rollback_strategy = "Set filled column values back to NULL and drop check"


def upgrade() -> None:
    # Backfill email for existing rows where missing, example policy only
    # This logic is domain-specific; adjust as needed for your data
    total = backfill_in_batches(
        table_name="users",
        set_sql="email = username || '@example.com'",
        where_sql="email IS NULL",
        order_by="id",
        batch_size=5000,
    )
    # Add a NOT VALID check to ensure no future NULLs arrive before contract
    add_check_not_valid(
        table_name="users",
        constraint_name="users_email_not_null_chk",
        check_sql="email IS NOT NULL",
    )
    # Optionally validate now (safe), or leave to contract phase
    from alembic_helpers.zero_downtime import validate_constraint
    validate_constraint("users", "users_email_not_null_chk")


def downgrade() -> None:
    # Relax constraint by dropping it if exists, and NULL-out backfilled values
    op.execute("ALTER TABLE \"users\" DROP CONSTRAINT IF EXISTS \"users_email_not_null_chk\";")
    # This is a simplistic rollback; in real cases you'd only null out rows changed by backfill
    op.execute("UPDATE \"users\" SET \"email\" = NULL;")

