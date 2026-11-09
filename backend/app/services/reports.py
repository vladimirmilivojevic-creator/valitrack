"""SQL reports: each report is a database view. The report page shows the rows and the view's SQL."""

import csv
import io

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.errors import NotFound
from app.services.common import to_jsonable

REPORTS: dict[str, dict] = {
    "validation-status": {
        "view": "vw_validation_status", "order": "application_name",
        "title": "Validation status",
        "question": "Where does each application stand in its validation?",
        "explain": "One row per application: requirement coverage, test results on the working version "
                   "and open deviations.",
    },
    "traceability": {
        "view": "vw_traceability", "order": "application_name, requirement_code, test_code",
        "title": "Traceability matrix",
        "question": "Which test covers which requirement, and what was the latest result?",
        "explain": "Requirement -> test case -> latest result. A requirement without a test shows an empty test column.",
    },
    "test-execution": {
        "view": "vw_test_execution_summary", "order": "application_name, version, test_type",
        "title": "Test execution summary",
        "question": "How did IQ, OQ and PQ go on each version?",
        "explain": "Counts of passed, failed and blocked tests per test type and version, using the latest run of each test.",
    },
    "open-changes": {
        "view": "vw_open_changes", "order": "age_days DESC",
        "title": "Open changes",
        "question": "Which changes are still open, how old are they and who are they waiting for?",
        "explain": "Every change request that is not released, rejected or cancelled.",
    },
    "training-compliance": {
        "view": "vw_training_compliance", "order": "application_name, full_name",
        "title": "Training compliance",
        "question": "Is everybody trained on the version that is live now?",
        "explain": "One row per user and application. 'Retraining needed' means the person was trained on an older version.",
    },
    "deviation-aging": {
        "view": "vw_deviation_aging", "order": "age_days DESC",
        "title": "Deviation aging",
        "question": "Which deviations are open and for how long?",
        "explain": "Open, in-progress and resolved deviations with their age and due date.",
    },
    "support-load": {
        "view": "vw_support_by_application", "order": "tickets_open DESC, application_name",
        "title": "Support load",
        "question": "Where do users need the most help?",
        "explain": "Tickets per application: open, defects, how-to questions and the average time to resolve.",
    },
    "audit-activity": {
        "view": "vw_audit_activity", "order": "day DESC, entity_type",
        "title": "Audit activity",
        "question": "What happened in the system, per day and type of record?",
        "explain": "Number of audit trail events and number of people per day and record type.",
    },
}


def catalog() -> list[dict]:
    return [{"key": key, **{k: v for k, v in info.items() if k in ("title", "question", "explain")}}
            for key, info in REPORTS.items()]


def run_report(db: Session, key: str) -> dict:
    info = REPORTS.get(key)
    if info is None:
        raise NotFound("Unknown report.")
    # The view name and the order come from the fixed table above, never from the request.
    result = db.execute(text(f"SELECT * FROM {info['view']} ORDER BY {info['order']}"))
    columns = list(result.keys())
    rows = [[to_jsonable(value) for value in row] for row in result]
    sql = db.scalar(text("SELECT pg_get_viewdef(CAST(:name AS regclass), true)"), {"name": info["view"]})
    return {
        "key": key, "title": info["title"], "question": info["question"], "explain": info["explain"],
        "view": info["view"], "columns": columns, "rows": rows,
        "sql": f"CREATE VIEW {info['view']} AS\n{sql}",
    }


def to_csv(columns: list[str], rows: list[list]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(columns)
    writer.writerows(rows)
    return buffer.getvalue()
