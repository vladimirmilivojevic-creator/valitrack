"""Training sessions and training records per application version."""

from datetime import UTC, datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import Conflict, Invalid
from app.models import (
    Application,
    AppVersion,
    TrainingAttendee,
    TrainingRecord,
    TrainingSession,
    User,
)
from app.services import audit, signatures
from app.services.common import canonical_hash, require_permission, require_text, row_dict, utcnow

SESSION_TYPES = ("classroom", "hands_on", "online", "read_and_understood")


def create_session(db: Session, user: User, application: Application, data: dict) -> TrainingSession:
    require_permission(user, "training.manage")
    if data.get("session_type") not in SESSION_TYPES:
        raise Invalid("Unknown training type.")
    version = db.get(AppVersion, data["app_version_id"])
    if version is None or version.application_id != application.id:
        raise Invalid("The version does not belong to this application.")
    if version.status not in ("validated", "in_validation"):
        raise Invalid("Training is planned for the live version or for the version that is being validated.")
    if db.get(User, data["trainer_id"]) is None:
        raise Invalid("The trainer does not exist.")
    session = TrainingSession(
        application_id=application.id, app_version_id=version.id,
        title=require_text(data.get("title"), "The title"), session_type=data["session_type"],
        trainer_id=data["trainer_id"], session_date=data["session_date"],
        duration_minutes=data.get("duration_minutes", 60), materials=data.get("materials"),
    )
    db.add(session)
    db.flush()
    for user_id in sorted(set(data.get("attendee_ids", []))):
        if db.get(User, user_id) is None:
            raise Invalid(f"User {user_id} does not exist.")
        db.add(TrainingAttendee(session_id=session.id, user_id=user_id))
    db.flush()
    audit.record(db, user, "create", "training_session", session.id, session.code,
                 new={**row_dict(session), "attendees": sorted(set(data.get("attendee_ids", [])))})
    return session


def attendees_of(db: Session, session_id: int) -> list[TrainingAttendee]:
    return list(db.scalars(select(TrainingAttendee).where(TrainingAttendee.session_id == session_id)
                           .order_by(TrainingAttendee.user_id)))


def complete_session(db: Session, user: User, password: str, session: TrainingSession,
                     attended_ids: list[int]):
    """The person who ran the session confirms who took part. Each attendee gets a training record."""
    require_permission(user, "training.manage")
    if session.status != "planned":
        raise Conflict("Only a planned session can be completed.")
    attendees = {a.user_id: a for a in attendees_of(db, session.id)}
    unknown = set(attended_ids) - set(attendees)
    if unknown:
        raise Invalid("Only invited people can be marked as present.")
    if not attended_ids:
        raise Invalid("Mark at least one person as present, or cancel the session.")
    application = db.get(Application, session.application_id)
    version = db.get(AppVersion, session.app_version_id)
    signature = signatures.sign(
        db, user, password, meaning="Training verified", entity_type="training_session",
        entity_id=session.id, entity_label=f"{session.code} {session.title}",
        record_hash=canonical_hash({"session": session.code, "version": version.version,
                                    "attended": sorted(attended_ids)}),
    )
    now = utcnow()
    # People were trained on the day of the session, even when the attendance is confirmed later.
    trained_on = datetime.combine(session.session_date, time(9, 0), tzinfo=UTC)
    if trained_on > now:
        trained_on = now
    for user_id, attendee in attendees.items():
        attendee.attended = user_id in attended_ids
    for user_id in attended_ids:
        record = db.scalar(select(TrainingRecord).where(
            TrainingRecord.app_version_id == version.id, TrainingRecord.user_id == user_id))
        if record is None:
            record = TrainingRecord(application_id=application.id, app_version_id=version.id, user_id=user_id)
            db.add(record)
        record.status = "completed"
        record.completed_at = trained_on
        record.session_id = session.id
    session.status = "completed"
    session.completed_at = now
    db.flush()
    audit.record(db, user, "complete", "training_session", session.id, session.code,
                 old={"status": "planned"},
                 new={"status": "completed", "trained": sorted(attended_ids), "version": version.version})
    return signature


def cancel_session(db: Session, user: User, session: TrainingSession, reason: str) -> None:
    require_permission(user, "training.manage")
    reason = require_text(reason, "A reason for cancelling")
    if session.status != "planned":
        raise Conflict("Only a planned session can be cancelled.")
    session.status = "cancelled"
    db.flush()
    audit.record(db, user, "cancel", "training_session", session.id, session.code,
                 old={"status": "planned"}, new={"status": "cancelled"}, reason=reason)
