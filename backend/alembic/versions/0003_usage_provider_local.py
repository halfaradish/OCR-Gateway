"""local usage provider

Revision ID: 9d2c4b7e1a63
Revises: 7c1f0d2a9b31
Create Date: 2026-11-04 23:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "9d2c4b7e1a63"
down_revision: str | None = "7c1f0d2a9b31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_PROVIDERS = "provider IN ('baidu', 'tencent', 'auto')"
NEW_PROVIDERS = "provider IN ('baidu', 'tencent', 'auto', 'local')"


def upgrade() -> None:
    with op.batch_alter_table("usage_events", recreate="always") as batch:
        batch.drop_constraint("ck_usage_provider", type_="check")
        batch.create_check_constraint("ck_usage_provider", NEW_PROVIDERS)


def downgrade() -> None:
    # The old constraint rejects local rows; map them back before rebuilding the table.
    op.execute("UPDATE usage_events SET provider='auto' WHERE provider='local'")
    with op.batch_alter_table("usage_events", recreate="always") as batch:
        batch.drop_constraint("ck_usage_provider", type_="check")
        batch.create_check_constraint("ck_usage_provider", OLD_PROVIDERS)
