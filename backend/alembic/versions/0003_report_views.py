"""SQL report views used by the dashboard and the Reports page

Revision ID: 0003
Revises: 0002
"""
from alembic import op
from app.core.db import run_sql_file

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_sql_file(op.get_bind(), "003_report_views.sql")


def downgrade() -> None:
    op.execute(
        """
        DROP VIEW IF EXISTS vw_audit_activity, vw_support_by_application, vw_deviation_aging,
            vw_training_compliance, vw_open_changes, vw_test_execution_summary, vw_traceability,
            vw_validation_status, vw_latest_runs;
        """
    )
