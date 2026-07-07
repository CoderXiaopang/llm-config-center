"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-07
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 运行时也会调用 SQLAlchemy create_all；迁移文件保留给生产库初始化。
    pass


def downgrade() -> None:
    pass

