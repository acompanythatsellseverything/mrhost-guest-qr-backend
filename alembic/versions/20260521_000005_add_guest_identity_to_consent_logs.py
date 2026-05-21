"""add guest identity to consent logs

Revision ID: 20260521_000005
Revises: 20260429_000004
Create Date: 2026-05-21 11:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260521_000005"
down_revision = "20260429_000004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "consent_logs",
        sa.Column("guest_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "consent_logs",
        sa.Column("guest_nationality", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("consent_logs", "guest_nationality")
    op.drop_column("consent_logs", "guest_name")
