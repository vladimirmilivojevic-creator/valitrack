"""Core tables: users, applications, requirements, tests, changes, training, support

Revision ID: 0001
Revises:
"""
from alembic import op
from app.core.db import run_sql_file

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_sql_file(op.get_bind(), "001_schema.sql")


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS e_signatures, report_documents, ticket_comments, support_tickets,
            training_records, training_attendees, training_sessions, config_items, deviations,
            evidence, test_run_steps, test_runs, change_test_links, change_impacts, change_requests,
            requirement_test_links, test_steps, test_cases, requirements, app_versions,
            application_users, applications, users CASCADE;
        DROP SEQUENCE IF EXISTS app_code_seq, cr_code_seq, dev_code_seq, ticket_code_seq,
            training_code_seq, report_code_seq;
        """
    )
