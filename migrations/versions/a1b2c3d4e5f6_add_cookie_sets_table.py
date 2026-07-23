"""add cookie_sets table

Revision ID: a1b2c3d4e5f6
Revises: 4e0f87e93b7a
Create Date: 2026-07-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '4e0f87e93b7a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('cookie_sets',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('source', sa.String(length=50), nullable=False),
    sa.Column('cookies', sa.JSON(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('minting_proxy', sa.String(length=255), nullable=True),
    sa.Column('user_agent', sa.String(length=512), nullable=True),
    sa.Column('impersonate_profile', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('success_count', sa.Integer(), nullable=False),
    sa.Column('failure_count', sa.Integer(), nullable=False),
    sa.Column('consecutive_failures', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_cookie_sets_source', 'cookie_sets', ['source'])
    op.create_index('ix_cookie_sets_status', 'cookie_sets', ['status'])
    op.create_index('ix_cookie_sets_expires_at', 'cookie_sets', ['expires_at'])
    op.create_index(
        'ix_cookie_sets_source_status_expires',
        'cookie_sets',
        ['source', 'status', 'expires_at'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_cookie_sets_source_status_expires', table_name='cookie_sets')
    op.drop_index('ix_cookie_sets_expires_at', table_name='cookie_sets')
    op.drop_index('ix_cookie_sets_status', table_name='cookie_sets')
    op.drop_index('ix_cookie_sets_source', table_name='cookie_sets')
    op.drop_table('cookie_sets')
