"""Numbers and lists for the start page."""

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models import (
    Application,
    AppVersion,
    AuditEntry,
    ChangeRequest,
    Deviation,
    SupportTicket,
    TestRun,
)
from app.services.common import to_jsonable
from app.services.gate import evaluate_release_gate

STAGES = ("requirements", "testing", "report", "release", "validated")

# The activity feed shows the steps that matter to a quality engineer, not every edit or login.
FEED_ACTIONS = ("sign", "status_change", "complete", "review", "validate", "supersede", "approve_urs",
                "approve", "close", "accept", "resolve", "generate", "assess", "plan_tests")


def _stage(db: Session, version: AppVersion) -> tuple[str, int]:
    """Where the version is in the lifecycle, and how many gate checks are still open."""
    gate = evaluate_release_gate(db, version.id)
    checks = {c.key: c.passed for c in gate.checks}
    open_checks = len(gate.failing())
    if version.status == "validated":
        return "validated", 0
    if not (checks["urs_approved"] and checks["risk_rated"]):
        return "requirements", open_checks
    if not gate.ready_for_report:
        return "testing", open_checks
    if not checks["report_approved"]:
        return "report", open_checks
    return "release", open_checks


def application_board(db: Session) -> list[dict]:
    board = []
    for application in db.scalars(select(Application).where(Application.status != "retired").order_by(Application.name)):
        versions = list(db.scalars(select(AppVersion).where(AppVersion.application_id == application.id)
                                   .order_by(AppVersion.id.desc())))
        live = next((v for v in versions if v.status == "validated"), None)
        working = next((v for v in versions if v.status == "in_validation"), None)
        focus = working or live
        stage, open_checks = _stage(db, focus) if focus else ("requirements", 0)
        board.append({
            "application_id": application.id, "code": application.code, "name": application.name,
            "gamp_category": application.gamp_category, "risk_class": application.risk_class,
            "live_version": live.version if live else None,
            "working_version": working.version if working else None,
            "working_version_id": working.id if working else None,
            "stage": stage, "open_checks": open_checks,
        })
    return board


def attention(db: Session) -> dict:
    awaiting_approval = db.scalar(select(func.count()).select_from(ChangeRequest)
                                  .where(ChangeRequest.status == "pending_approval"))
    open_changes = db.scalar(select(func.count()).select_from(ChangeRequest)
                             .where(ChangeRequest.status.in_(
                                 ["draft", "submitted", "impact_assessment", "pending_approval", "approved",
                                  "testing", "ready_for_release"])))
    open_deviations = db.scalar(select(func.count()).select_from(Deviation)
                                .where(Deviation.status.in_(["open", "in_progress", "resolved"])))
    unreviewed = db.scalar(select(func.count()).select_from(TestRun)
                           .where(TestRun.status == "completed", TestRun.reviewed_at.is_(None)))
    open_tickets = db.scalar(select(func.count()).select_from(SupportTicket)
                             .where(SupportTicket.status.in_(["open", "in_progress", "waiting_user"])))
    training_gaps = db.scalar(text(
        "SELECT count(*) FROM vw_training_compliance WHERE training_status IN ('not_trained', 'retraining_needed')"))
    return {
        "open_changes": open_changes, "changes_awaiting_approval": awaiting_approval,
        "open_deviations": open_deviations, "runs_awaiting_review": unreviewed,
        "open_tickets": open_tickets, "training_gaps": training_gaps,
    }


def recent_activity(db: Session, limit: int = 12) -> list[dict]:
    rows = db.scalars(select(AuditEntry).where(AuditEntry.action.in_(FEED_ACTIONS))
                      .order_by(AuditEntry.seq.desc()).limit(limit))
    return [to_jsonable({
        "seq": e.seq, "occurred_at": e.occurred_at, "actor_name": e.actor_name, "action": e.action,
        "entity_type": e.entity_type, "entity_label": e.entity_label,
    }) for e in rows]


def build_dashboard(db: Session) -> dict:
    return {"board": application_board(db), "attention": attention(db), "activity": recent_activity(db)}
