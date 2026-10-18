"""Add logo to default_model_role enum."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0014_default_model_logo"
down_revision: str | None = "0013_collections"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # MySQL: extend ENUM. Keep historical values (incl. embedding from 0003).
    op.execute(
        sa.text(
            "ALTER TABLE default_models MODIFY COLUMN role "
            "ENUM('chat','stt','tts','embedding','logo') NOT NULL"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM default_models WHERE role = 'logo'"))
    op.execute(
        sa.text(
            "ALTER TABLE default_models MODIFY COLUMN role "
            "ENUM('chat','stt','tts','embedding') NOT NULL"
        )
    )
