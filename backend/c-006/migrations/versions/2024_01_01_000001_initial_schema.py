from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '2024_01_01_000001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    op.create_table(
        'posts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('published', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'title', name='uq_user_title'),
    )
    op.create_index('ix_posts_user_id', 'posts', ['user_id'], unique=False)
    op.create_index('ix_posts_published_created_at', 'posts', ['published', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_posts_published_created_at', table_name='posts')
    op.drop_index('ix_posts_user_id', table_name='posts')
    op.drop_table('posts')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')

