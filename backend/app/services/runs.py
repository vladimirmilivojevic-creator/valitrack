"""Test execution: run a test case step by step, attach evidence, sign, get it reviewed."""

import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import Conflict, Forbidden, Invalid
from app.models import (
    AppVersion,
    Evidence,
    Requirement,
    RequirementTestLink,
    TestCase,
    TestRun,
    TestRunStep,
    User,
)
from app.services import audit, signatures
from app.services.common import canonical_hash, require_permission, require_text, utcnow
from app.services.deviations import create_from_failed_run

STEP_RESULTS = ("passed", "failed", "blocked", "na")
EVIDENCE_TYPES = {"image/png", "image/jpeg", "application/pdf", "text/plain"}


def start_run(db: Session, user: User, test_case: TestCase, version: AppVersion,
              change_request_id: int | None = None) -> TestRun:
    require_permission(user, "run.execute")
    if test_case.status != "approved":
        raise Conflict("Only an approved test case can be executed.")
    if version.application_id != test_case.application_id:
        raise Invalid("The test case and the version belong to different applications.")
    if version.status != "in_validation":
        raise Conflict("Tests can only be executed on a version that is in validation.")
    open_run = db.scalar(
        select(TestRun).where(
            TestRun.test_case_id == test_case.id, TestRun.app_version_id == version.id,
            TestRun.status == "in_progress",
        )
    )
    if open_run is not None:
        raise Conflict(f"Run {open_run.id} of this test is still in progress on this version.")
    run = TestRun(
        test_case_id=test_case.id, test_case_revision=test_case.revision, app_version_id=version.id,
        change_request_id=change_request_id, executed_by=user.id,
    )
    if test_case.style == "unscripted":
        run.steps.append(TestRunStep(
            step_no=1, action=f"Exploratory session: {test_case.objective}",
            expected_result="No unexpected behaviour. Describe what you did and what you saw.",
        ))
    else:
        for step in test_case.steps:
            run.steps.append(TestRunStep(
                step_no=step.step_no, action=step.action, expected_result=step.expected_result))
    db.add(run)
    db.flush()
    audit.record(db, user, "start", "test_run", run.id, f"{test_case.code} on {version.version}",
                 new={"test_case": test_case.code, "revision": test_case.revision, "version": version.version})
    return run


def _own_open_run(user: User, run: TestRun) -> None:
    if run.status != "in_progress":
        raise Conflict("This run is already completed and can no longer be changed.")
    if run.executed_by != user.id:
        raise Forbidden("Only the person who started the run can record results.")


def get_step(run: TestRun, step_no: int) -> TestRunStep:
    for step in run.steps:
        if step.step_no == step_no:
            return step
    raise Invalid(f"The run has no step {step_no}.")


def record_step(db: Session, user: User, run: TestRun, step_no: int, result: str,
                actual_result: str | None, comment: str | None) -> TestRunStep:
    require_permission(user, "run.execute")
    _own_open_run(user, run)
    if result not in STEP_RESULTS:
        raise Invalid("The result must be passed, failed, blocked or na.")
    step = get_step(run, step_no)
    if result in ("failed", "blocked"):
        require_text(actual_result, "The actual result")
    old = {"result": step.result, "actual_result": step.actual_result}
    step.result = result
    step.actual_result = actual_result
    step.comment = comment
    step.executed_at = utcnow()
    db.flush()
    audit.record(db, user, "record_step", "test_run", run.id, f"run {run.id} step {step_no}",
                 old=old, new={"result": result, "actual_result": actual_result})
    return step


def add_evidence(db: Session, user: User, run: TestRun, step_no: int, filename: str,
                 content_type: str, data: bytes) -> Evidence:
    require_permission(user, "run.execute")
    _own_open_run(user, run)
    if content_type not in EVIDENCE_TYPES:
        raise Invalid("Evidence must be a PNG or JPEG image, a PDF or a text file.")
    if not data:
        raise Invalid("The file is empty.")
    if len(data) > get_settings().max_evidence_bytes:
        raise Invalid("The file is larger than 2 MB.")
    step = get_step(run, step_no)
    evidence = Evidence(
        run_step_id=step.id, filename=filename[:200], content_type=content_type, size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(), data=data, uploaded_by=user.id,
    )
    db.add(evidence)
    db.flush()
    audit.record(db, user, "upload_evidence", "test_run", run.id, f"run {run.id} step {step_no}",
                 new={"filename": evidence.filename, "sha256": evidence.sha256, "bytes": evidence.size_bytes})
    return evidence


def evidence_of_run(db: Session, run: TestRun) -> list[Evidence]:
    step_ids = [s.id for s in run.steps]
    if not step_ids:
        return []
    return list(db.scalars(select(Evidence).where(Evidence.run_step_id.in_(step_ids)).order_by(Evidence.id)))


def run_snapshot(db: Session, run: TestRun) -> dict:
    """What the execution signature covers: every step result and the hash of every evidence file."""
    evidence = evidence_of_run(db, run)
    return {
        "run": run.id, "test_case": run.test_case_id, "revision": run.test_case_revision,
        "version": run.app_version_id, "result": run.result,
        "steps": [[s.step_no, s.action, s.expected_result, s.actual_result, s.result, s.comment]
                  for s in run.steps],
        "evidence": sorted([e.run_step_id, e.sha256] for e in evidence),
    }


def complete_run(db: Session, user: User, password: str, run: TestRun, comment: str | None = None):
    require_permission(user, "run.execute")
    _own_open_run(user, run)
    pending = [s.step_no for s in run.steps if s.result == "pending"]
    if pending:
        raise Conflict(f"Record a result for every step first. Open steps: {', '.join(map(str, pending))}.")
    results = {s.result for s in run.steps}
    outcome = "failed" if "failed" in results else "blocked" if "blocked" in results else "passed"
    test_case = db.get(TestCase, run.test_case_id)
    run.result = outcome
    run.status = "completed"
    run.completed_at = utcnow()
    db.flush()
    signature = signatures.sign(
        db, user, password, meaning="Executed", entity_type="test_run", entity_id=run.id,
        entity_label=f"{test_case.code} run {run.id}", record_hash=canonical_hash(run_snapshot(db, run)),
        comment=comment,
    )
    audit.record(db, user, "complete", "test_run", run.id, f"{test_case.code} run {run.id}",
                 old={"status": "in_progress"}, new={"status": "completed", "result": outcome})
    if outcome == "failed":
        create_from_failed_run(db, user, run, test_case, _worst_risk(db, test_case))
    return signature


def _worst_risk(db: Session, test_case: TestCase) -> str | None:
    levels = set(db.scalars(
        select(Requirement.risk_level)
        .join(RequirementTestLink, RequirementTestLink.requirement_id == Requirement.id)
        .where(RequirementTestLink.test_case_id == test_case.id)
    ))
    for level in ("high", "medium", "low"):
        if level in levels:
            return level
    return None


def review_run(db: Session, user: User, password: str, run: TestRun, comment: str | None = None):
    require_permission(user, "run.review")
    if run.status != "completed":
        raise Conflict("Only a completed run can be reviewed.")
    if run.reviewed_at is not None:
        raise Conflict("This run has already been reviewed.")
    signatures.forbid_same_person(user, run.executed_by, "The person who executed a test cannot review it.")
    test_case = db.get(TestCase, run.test_case_id)
    signature = signatures.sign(
        db, user, password, meaning="Reviewed", entity_type="test_run", entity_id=run.id,
        entity_label=f"{test_case.code} run {run.id}", record_hash=canonical_hash(run_snapshot(db, run)),
        comment=comment,
    )
    run.reviewed_by = user.id
    run.reviewed_at = utcnow()
    run.review_comment = comment
    db.flush()
    audit.record(db, user, "review", "test_run", run.id, f"{test_case.code} run {run.id}",
                 new={"reviewed_by": user.id})
    return signature
