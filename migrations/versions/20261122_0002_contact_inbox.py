"""Add contact inbox storage without touching existing student records.

Revision ID: 20261122_0002
Revises: 20261121_0001
"""
from alembic import op
import sqlalchemy as sa

revision = "20261122_0002"
down_revision = "20261121_0001"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("contact_messages"):
        op.create_table("contact_messages",
                        sa.Column("id", sa.Integer(), primary_key=True),
                        sa.Column("name", sa.String(100), nullable=False),
                        sa.Column("email", sa.String(254), nullable=False),
                        sa.Column("message", sa.Text(), nullable=False),
                        sa.Column("email_sent", sa.Boolean(), nullable=False, server_default=sa.false()),
                        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
        op.create_index("ix_contact_messages_created_at", "contact_messages", ["created_at"])


def downgrade():
    # Intentionally retain user-submitted messages; remove manually only after backup.
    pass
