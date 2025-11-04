from alembic import op
import sqlalchemy as sa

# Revision identifiers, used by Alembic.
revision = "0000_initial"
down_revision = None
branch_labels = None
depends_on = None
phase = "expand"  # initial
rollback_strategy = "Drop created objects"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    # Initial unique index on username (safe because table is empty at bootstrap)
    op.create_index("ux_users_username", "users", ["username"], unique=True)


def downgrade() -> None:
    op.drop_index("ux_users_username", table_name="users")
    op.drop_table("users")

