from alembic import op
from alembic_helpers.zero_downtime import set_not_null, drop_not_null

# Revision identifiers, used by Alembic.
revision = "0003_contract_enforce_email_not_null"
down_revision = "0002_migrate_backfill_email"
branch_labels = None
depends_on = None
phase = "contract"
rollback_strategy = "Drop NOT NULL, keep index and column for safety"


def upgrade() -> None:
    # Ensure the NOT VALID check was added and validated in migrate phase.
    # Now set NOT NULL which should be instantaneous if validated.
    set_not_null("users", "email")
    # Drop the transitional check constraint if it exists; NOT NULL supersedes it.
    op.execute("ALTER TABLE \"users\" DROP CONSTRAINT IF EXISTS \"users_email_not_null_chk\";")


def downgrade() -> None:
    # Allow NULLs again
    drop_not_null("users", "email")
    # Recreate the transitional check (NOT VALID) to keep guardrails in place
    op.execute(
        "ALTER TABLE \"users\" ADD CONSTRAINT \"users_email_not_null_chk\" CHECK (email IS NOT NULL) NOT VALID;"
    )

