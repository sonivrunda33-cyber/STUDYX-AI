"""Create the initial StudyX AI workspace schema.

Revision ID: 20261121_0001
Revises:
Create Date: 2026-11-21
"""
from alembic import op

from app.extensions import db

revision = "20261121_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Keep table definitions in the ORM so the initial schema stays aligned
    # with the model relationships and works for SQLite and PostgreSQL.
    db.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade():
    db.metadata.drop_all(bind=op.get_bind(), checkfirst=True)
