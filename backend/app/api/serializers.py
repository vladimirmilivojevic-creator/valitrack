"""Turn database objects into JSON. Kept separate from the routes so the routes stay short."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Application,
    ApplicationUser,
    AppVersion,
    ChangeRequest,
    ChangeTestLink,
    ConfigItem,
    Deviation,
    ESignature,
    ReportDocument,
    Requirement,
    RequirementTestLink,
    SupportTicket,
    TestCase,
    TestRun,
    TrainingSession,
    User,
)
from app.services import changes, gamp, signatures, testcases, training
from app.services.common import row_dict, utcnow
from app.services.runs import evidence_of_run


def user_out(user: User) -> dict:
    out = row_dict(user, exclude=("failed_logins",))
    out["locked"] = bool(user.locked_until and user.locked_until > utcnow())
    return out


def signature_out(signature: ESignature) -> dict:
    return row_dict(signature)


def version_out(version: AppVersion) -> dict:
    return row_dict(version)


def application_out(db: Session, application: Application, detail: bool = False) -> dict:
    out = row_dict(application)
    out["owner_name"] = application.owner.full_name if application.owner else None
    info = gamp.GAMP_CATEGORIES[application.gamp_category]
    out["gamp_name"] = info["name"]
    out["required_tests"] = list(info["required_tests"])
    versions = list(db.scalars(select(AppVersion).where(AppVersion.application_id == application.id)
                               .order_by(AppVersion.id.desc())))
    live = next((v for v in versions if v.status == "validated"), None)
    working = next((v for v in versions if v.status == "in_validation"), None)
    out["live_version"] = version_out(live) if live else None
    out["working_version"] = version_out(working) if working else None
    if detail:
        out["approach"] = gamp.validation_approach(application.gamp_category, application.risk_class)
        out["versions"] = [version_out(v) for v in versions]
        out["users"] = [
            {"user_id": a.user_id, "app_role": a.app_role}
            for a in db.scalars(select(ApplicationUser).where(ApplicationUser.application_id == application.id))
        ]
    return out


def requirement_out(db: Session, requirement: Requirement) -> dict:
    out = row_dict(requirement)
    ids = list(db.scalars(select(RequirementTestLink.test_case_id)
                          .where(RequirementTestLink.requirement_id == requirement.id)))
    codes = {t.id: t.code for t in db.scalars(select(TestCase).where(TestCase.id.in_(ids)))} if ids else {}
    out["test_case_ids"] = sorted(ids)
    out["test_codes"] = sorted(codes.values())
    return out


def test_case_out(db: Session, test_case: TestCase) -> dict:
    out = row_dict(test_case)
    out["steps"] = [{"step_no": s.step_no, "action": s.action, "expected_result": s.expected_result}
                    for s in test_case.steps]
    out["requirement_ids"] = testcases.linked_requirement_ids(db, test_case.id)
    return out


def run_out(db: Session, run: TestRun) -> dict:
    out = row_dict(run)
    test_case = db.get(TestCase, run.test_case_id)
    version = db.get(AppVersion, run.app_version_id)
    out["test_code"] = test_case.code
    out["test_title"] = test_case.title
    out["test_type"] = test_case.test_type
    out["test_style"] = test_case.style
    out["application_id"] = test_case.application_id
    out["version"] = version.version
    evidence = evidence_of_run(db, run)
    by_step: dict[int, list[dict]] = {}
    for e in evidence:
        by_step.setdefault(e.run_step_id, []).append(
            {"id": e.id, "filename": e.filename, "content_type": e.content_type,
             "size_bytes": e.size_bytes, "sha256": e.sha256, "uploaded_at": e.uploaded_at.isoformat()})
    out["steps"] = [
        {
            "step_no": s.step_no, "action": s.action, "expected_result": s.expected_result,
            "actual_result": s.actual_result, "result": s.result, "comment": s.comment,
            "executed_at": s.executed_at.isoformat() if isinstance(s.executed_at, datetime) else None,
            "evidence": by_step.get(s.id, []),
        }
        for s in run.steps
    ]
    out["signatures"] = [signature_out(s) for s in signatures.signatures_for(db, "test_run", run.id)]
    return out


def deviation_out(db: Session, deviation: Deviation) -> dict:
    out = row_dict(deviation)
    out["signatures"] = [signature_out(s) for s in signatures.signatures_for(db, "deviation", deviation.id)]
    return out


def change_out(db: Session, change: ChangeRequest, detail: bool = False) -> dict:
    out = row_dict(change)
    application = db.get(Application, change.application_id)
    out["application_name"] = application.name
    out["impacts"] = [row_dict(i) for i in change.impacts]
    out["required_signatures"] = changes.required_meanings(change)
    out["signatures"] = [signature_out(s) for s in signatures.signatures_for(db, "change_request", change.id)]
    if detail:
        out["test_case_ids"] = [
            row.test_case_id for row in db.scalars(select(ChangeTestLink).where(ChangeTestLink.change_id == change.id))
        ]
    return out


def config_out(item: ConfigItem) -> dict:
    return row_dict(item)


def ticket_out(ticket: SupportTicket) -> dict:
    out = row_dict(ticket)
    out["comments"] = [row_dict(c) for c in ticket.comments]
    return out


def session_out(db: Session, session: TrainingSession) -> dict:
    out = row_dict(session)
    out["attendees"] = [{"user_id": a.user_id, "attended": a.attended} for a in training.attendees_of(db, session.id)]
    return out


def report_doc_out(document: ReportDocument) -> dict:
    return row_dict(document)
