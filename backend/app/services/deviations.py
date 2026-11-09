"""Deviations (something went wrong or differs from the plan) with root cause and CAPA fields.

CAPA = corrective and preventive action: fix the problem now, and change something so it does not return.
"""

from sqlalchemy.orm import Session

from app.core.errors import Conflict, Invalid
from app.models import Deviation, TestCase, TestRun, User
from app.services import audit, signatures
from app.services.common import canonical_hash, require_permission, require_text, row_dict

OPEN_STATUSES = ("open", "in_progress", "resolved")
EDITABLE = ("title", "description", "severity", "root_cause", "impact", "corrective_action",
            "preventive_action", "owner_id", "due_date")


def _severity(value: str) -> str:
    if value not in ("minor", "major", "critical"):
        raise Invalid("The severity must be minor, major or critical.")
    return value


def create_deviation(db: Session, user: User, data: dict) -> Deviation:
    require_permission(user, "deviation.write")
    deviation = Deviation(
        application_id=data["application_id"],
        app_version_id=data.get("app_version_id"),
        test_run_id=data.get("test_run_id"),
        source="manual",
        title=require_text(data.get("title"), "The title"),
        description=require_text(data.get("description"), "The description"),
        severity=_severity(data.get("severity", "minor")),
        owner_id=data.get("owner_id") or user.id,
        due_date=data.get("due_date"),
        created_by=user.id,
    )
    db.add(deviation)
    db.flush()
    audit.record(db, user, "create", "deviation", deviation.id, deviation.code, new=row_dict(deviation))
    return deviation


def create_from_failed_run(db: Session, user: User, run: TestRun, test_case: TestCase,
                           worst_risk: str | None) -> Deviation:
    """A failed test always opens a deviation, so a failure cannot be forgotten."""
    failed = [s for s in run.steps if s.result == "failed"]
    detail = "; ".join(f"step {s.step_no}: {s.actual_result}" for s in failed)
    deviation = Deviation(
        application_id=test_case.application_id,
        app_version_id=run.app_version_id,
        test_run_id=run.id,
        source="test_failure",
        title=f"{test_case.code} failed: {test_case.title}",
        description=f"Test run {run.id} failed. {detail}",
        severity="major" if worst_risk == "high" else "minor",
        owner_id=user.id,
        created_by=user.id,
    )
    db.add(deviation)
    db.flush()
    audit.record(db, user, "create", "deviation", deviation.id, deviation.code,
                 new={**row_dict(deviation), "opened_by": "failed test run"})
    return deviation


def update_deviation(db: Session, user: User, deviation: Deviation, data: dict, reason: str) -> Deviation:
    require_permission(user, "deviation.write")
    reason = require_text(reason, "A reason for the change")
    if deviation.status in ("closed", "accepted"):
        raise Conflict("A closed deviation cannot be changed.")
    if "severity" in data:
        _severity(data["severity"])
    before = row_dict(deviation)
    for key in EDITABLE:
        if key in data:
            setattr(deviation, key, data[key])
    if deviation.status == "open" and (deviation.root_cause or deviation.corrective_action):
        deviation.status = "in_progress"
    db.flush()
    old, new = audit.changed_fields(before, row_dict(deviation))
    if new:
        audit.record(db, user, "update", "deviation", deviation.id, deviation.code, old, new, reason)
    return deviation


def resolve_deviation(db: Session, user: User, deviation: Deviation) -> Deviation:
    """The owner says the problem is fixed. QA still has to close it."""
    require_permission(user, "deviation.write")
    if deviation.status not in ("open", "in_progress"):
        raise Conflict("Only an open deviation can be marked as resolved.")
    if not (deviation.root_cause and deviation.corrective_action):
        raise Conflict("Describe the root cause and the corrective action first.")
    deviation.status = "resolved"
    db.flush()
    audit.record(db, user, "resolve", "deviation", deviation.id, deviation.code,
                 old={"status": "in_progress"}, new={"status": "resolved"})
    return deviation


def _snapshot(deviation: Deviation) -> str:
    return canonical_hash({k: v for k, v in row_dict(deviation).items()
                           if k in ("code", "title", "description", "severity", "root_cause", "impact",
                                    "corrective_action", "preventive_action")})


def close_deviation(db: Session, user: User, password: str, deviation: Deviation, comment: str):
    require_permission(user, "deviation.close")
    comment = require_text(comment, "A closure comment")
    if deviation.status != "resolved":
        raise Conflict("A deviation must be resolved before QA can close it.")
    signature = signatures.sign(
        db, user, password, meaning="Closed", entity_type="deviation", entity_id=deviation.id,
        entity_label=deviation.code, record_hash=_snapshot(deviation), comment=comment,
    )
    deviation.status = "closed"
    deviation.closure_comment = comment
    deviation.closed_at = signature.signed_at
    db.flush()
    audit.record(db, user, "close", "deviation", deviation.id, deviation.code,
                 old={"status": "resolved"}, new={"status": "closed"}, reason=comment)
    return signature


def accept_deviation(db: Session, user: User, password: str, deviation: Deviation, justification: str):
    """QA accepts the deviation without a fix. The reason is recorded with a signature."""
    require_permission(user, "deviation.close")
    justification = require_text(justification, "A justification", 10)
    if deviation.status not in ("open", "in_progress", "resolved"):
        raise Conflict("This deviation is already closed.")
    signature = signatures.sign(
        db, user, password, meaning="Approved", entity_type="deviation", entity_id=deviation.id,
        entity_label=f"{deviation.code} accepted", record_hash=_snapshot(deviation), comment=justification,
    )
    old_status = deviation.status
    deviation.status = "accepted"
    deviation.closure_comment = justification
    deviation.closed_at = signature.signed_at
    db.flush()
    audit.record(db, user, "accept", "deviation", deviation.id, deviation.code,
                 old={"status": old_status}, new={"status": "accepted"}, reason=justification)
    return signature
