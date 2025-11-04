from alembic import op
import sqlalchemy as sa
from alembic_helpers.zero_downtime import add_column_nullable, create_index_concurrently

# Revision identifiers, used by Alembic.
revision = "0001_expand_add_email_column"
down_revision = "0000_initial"
branch_labels = None
depends_on = None
phase = "expand"
rollback_strategy = "Drop newly added column and related indexes"


def upgrade() -> None:
    # Expand: add nullable column; avoid default to prevent table rewrite
    add_column_nullable(
        "users",
        sa.Column("email", sa.String(length=320), nullable=True),
    )
    # Add a partial unique index on email to allow multiple NULLs and uniqueness for non-NULL
    create_index_concurrently(
        index_name="ux_users_email",
        table_name="users",
        columns=["email"],
        unique=True,
        where="email IS NOT NULL",
    )


def downgrade() -> None:
    # Remove index concurrently then drop column
    from alembic_helpers.zero_downtime import drop_index_concurrently

    drop_index_concurrently("ux_users_email")
    op.drop_column("users", "email")

