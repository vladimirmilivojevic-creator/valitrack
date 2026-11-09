"""User requirements (URS), functional specifications (FS) and their risk rating."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import Conflict, Invalid
from app.models import Application, Requirement, User
from app.services import audit
from app.services.common import require_permission, require_text, row_dict

RATING_FIELDS = ("severity", "probability", "detectability")


def _check_ratings(data: dict) -> None:
    for field in RATING_FIELDS:
        value = data.get(field)
        if value is not None and value not in (1, 2, 3):
            raise Invalid(f"{field.capitalize()} must be 1, 2 or 3.")


def next_code(db: Session, application_id: int, kind: str) -> str:
    count = db.scalar(
        select(func.count()).select_from(Requirement)
        .where(Requirement.application_id == application_id, Requirement.kind == kind)
    )
    return f"{kind}-{count + 1:03d}"


def create_requirement(db: Session, user: User, application: Application, data: dict) -> Requirement:
    require_permission(user, "req.write")
    _check_ratings(data)
    kind = data.get("kind", "URS")
    if kind not in ("URS", "FS"):
        raise Invalid("The kind must be URS or FS.")
    parent_id = data.get("parent_id")
    if kind == "FS":
        parent = db.get(Requirement, parent_id) if parent_id else None
        if parent is None or parent.application_id != application.id or parent.kind != "URS":
            raise Invalid("A functional specification must belong to a requirement (URS) of the same application.")
    elif parent_id:
        raise Invalid("Only a functional specification can have a parent.")
    requirement = Requirement(
        application_id=application.id,
        code=next_code(db, application.id, kind),
        kind=kind,
        parent_id=parent_id,
        title=require_text(data.get("title"), "The title"),
        description=require_text(data.get("description"), "The description"),
        severity=data.get("severity"),
        probability=data.get("probability"),
        detectability=data.get("detectability"),
        created_by=user.id,
    )
    db.add(requirement)
    db.flush()
    audit.record(db, user, "create", "requirement", requirement.id,
                 f"{application.name} {requirement.code}", new=row_dict(requirement))
    return requirement


def update_requirement(db: Session, user: User, requirement: Requirement, data: dict, reason: str) -> Requirement:
    require_permission(user, "req.write")
    reason = require_text(reason, "A reason for the change")
    if requirement.status == "retired":
        raise Conflict("A retired requirement cannot be changed.")
    _check_ratings(data)
    before = row_dict(requirement)
    for key in ("title", "description", *RATING_FIELDS):
        if key in data:
            setattr(requirement, key, data[key])
    db.flush()
    db.refresh(requirement)  # read the risk level that the database calculated
    old, new = audit.changed_fields(before, row_dict(requirement))
    if new:
        audit.record(db, user, "update", "requirement", requirement.id, requirement.code, old, new, reason)
    return requirement


def retire_requirement(db: Session, user: User, requirement: Requirement, reason: str) -> Requirement:
    require_permission(user, "req.write")
    reason = require_text(reason, "A reason for retiring the requirement")
    if requirement.status == "retired":
        raise Conflict("The requirement is already retired.")
    requirement.status = "retired"
    db.flush()
    audit.record(db, user, "retire", "requirement", requirement.id, requirement.code,
                 old={"status": "active"}, new={"status": "retired"}, reason=reason)
    return requirement
