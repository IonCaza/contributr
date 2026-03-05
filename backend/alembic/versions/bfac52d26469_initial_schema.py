"""initial schema

Revision ID: bfac52d26469
Revises:
Create Date: 2026-03-04 18:32:08.515943
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "bfac52d26469"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.db.base import Base
    import app.db.models  # noqa: F401

    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    from app.db.base import Base
    import app.db.models  # noqa: F401

    Base.metadata.drop_all(bind=op.get_bind(), checkfirst=True)
