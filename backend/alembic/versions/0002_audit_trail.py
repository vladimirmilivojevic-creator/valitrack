"""Audit trail with hash chain, signature stamping and append-only triggers

Revision ID: 0002
Revises: 0001
"""
from alembic import op
from app.core.db import run_sql_file

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_sql_file(op.get_bind(), "002_audit_trail.sql")


def downgrade() -> None:
    op.execute(
        """
        DROP FUNCTION IF EXISTS verify_audit_chain();
        DROP TRIGGER IF EXISTS e_signatures_stamp ON e_signatures;
        DROP TRIGGER IF EXISTS e_signatures_no_change ON e_signatures;
        DROP TRIGGER IF EXISTS e_signatures_no_truncate ON e_signatures;
        DROP TABLE IF EXISTS audit_log CASCADE;
        DROP FUNCTION IF EXISTS e_signatures_before_insert();
        DROP FUNCTION IF EXISTS forbid_truncate();
        DROP FUNCTION IF EXISTS forbid_change();
        DROP FUNCTION IF EXISTS audit_log_before_insert();
        DROP FUNCTION IF EXISTS audit_entry_hash(text, bigint, timestamptz, integer, text, text, text, text, text, jsonb, jsonb, text);
        """
    )
