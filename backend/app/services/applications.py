"""Applications, versions, the requirements baseline approval and version release."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import Conflict, Invalid, NotFound
from app.core.permissions import DEPARTMENTS
from app.models import (
    Application,
    ApplicationUser,
    AppVersion,
    ChangeRequest,
    TrainingRecord,
    User,
)
from app.services import audit, signatures
from app.services.common import (
    canonical_hash,
    require_permission,
    require_text,
    row_dict,
    utcnow,
)
from app.services.gamp import GAMP_CATEGORIES
from app.services.gate import baseline_hash, evaluate_release_gate, requirements_baseline

APP_FIELDS = (
    "name", "description", "vendor", "department", "owner_id", "gamp_category", "intended_use",
    "patient_safety_impact", "product_quality_impact", "data_integrity_impact", "status",
)


def _check_application_data(db: Session, data: dict) -> None:
    if "gamp_category" in data and data["gamp_category"] not in GAMP_CATEGORIES:
        raise Invalid("GAMP category must be 1, 3, 4 or 5.")
    if "department" in data and data["department"] not in DEPARTMENTS:
        raise Invalid("Unknown department.")
    if "owner_id" in data and db.get(User, data["owner_id"]) is None:
        raise Invalid("The owner does not exist.")


def create_application(db: Session, user: User, data: dict, initial_version: str | None = None) -> Application:
    require_permission(user, "app.write")
    _check_application_data(db, data)
    if db.scalar(select(Application).where(Application.name == data["name"])):
        raise Conflict("An application with this name already exists.")
    application = Application(**{k: data[k] for k in APP_FIELDS if k in data})
    db.add(application)
    db.flush()
    audit.record(db, user, "create", "application", application.id, application.name,
                 new=row_dict(application))
    if initial_version:
        create_version(db, user, application, initial_version)
    return application


def update_application(db: Session, user: User, application: Application, data: dict, reason: str) -> Application:
    require_permission(user, "app.write")
    reason = require_text(reason, "A reason for the change")
    _check_application_data(db, data)
    before = row_dict(application)
    for key, value in data.items():
        if key in APP_FIELDS:
            setattr(application, key, value)
    db.flush()
    old, new = audit.changed_fields(before, row_dict(application))
    if new:
        audit.record(db, user, "update", "application", application.id, application.name, old, new, reason)
    return application


def create_version(db: Session, user: User, application: Application, version: str,
                   release_notes: str | None = None) -> AppVersion:
    require_permission(user, "app.write")
    version = require_text(version, "The version number", 1)
    existing = db.scalars(select(AppVersion).where(AppVersion.application_id == application.id)).all()
    if any(v.version == version for v in existing):
        raise Conflict(f"Version {version} already exists for {application.name}.")
    if any(v.status == "in_validation" for v in existing):
        raise Conflict("Another version of this application is still in validation.")
    new_version = AppVersion(
        application_id=application.id, version=version, release_notes=release_notes, created_by=user.id
    )
    db.add(new_version)
    db.flush()
    audit.record(db, user, "create", "app_version", new_version.id,
                 f"{application.name} {version}", new=row_dict(new_version))
    return new_version


def approve_urs(db: Session, user: User, password: str, version: AppVersion, comment: str | None = None):
    """QA approves the requirements baseline. Later changes to it are detected by the release gate."""
    require_permission(user, "req.approve")
    if version.status != "in_validation":
        raise Conflict("Only a version that is in validation can have its requirements approved.")
    application = db.get(Application, version.application_id)
    current = baseline_hash(db, application.id)
    items = requirements_baseline(db, application.id)
    if not items:
        raise Conflict("There are no requirements to approve.")
    unrated = [i["code"] for i in items if None in (i["severity"], i["probability"], i["detectability"])]
    if unrated:
        raise Conflict(f"The risk assessment is incomplete: {', '.join(unrated[:5])} have no risk rating.")
    signatures.forbid_same_person(
        user, version.created_by, "The person who prepared the version cannot approve its requirements."
    )
    signature = signatures.sign(
        db, user, password, meaning="Approved", entity_type="requirements_baseline", entity_id=version.id,
        entity_label=f"{application.name} {version.version} requirements", record_hash=current, comment=comment,
    )
    version.urs_approved = True
    version.urs_baseline_hash = current
    version.urs_approved_at = signature.signed_at
    audit.record(db, user, "approve_urs", "app_version", version.id, f"{application.name} {version.version}",
                 new={"baseline_hash": current, "requirements": len(items)})
    return signature


def apply_release(db: Session, user: User, version: AppVersion) -> None:
    """Make a version the live validated version. Shared by direct release and change release."""
    application = db.get(Application, version.application_id)
    previous = db.scalars(
        select(AppVersion).where(AppVersion.application_id == application.id, AppVersion.status == "validated")
    ).all()
    for old in previous:
        old.status = "superseded"
        audit.record(db, user, "supersede", "app_version", old.id, f"{application.name} {old.version}",
                     old={"status": "validated"}, new={"status": "superseded"})
    db.flush()
    version.status = "validated"
    version.validated_at = utcnow()
    db.flush()
    audit.record(db, user, "validate", "app_version", version.id, f"{application.name} {version.version}",
                 old={"status": "in_validation"}, new={"status": "validated"})
    _require_retraining(db, user, application, version, {v.id for v in previous})


def _require_retraining(db: Session, user: User, application: Application, version: AppVersion,
                        previous_ids: set[int]) -> None:
    """Everybody who was trained on an earlier version must be trained on the new one."""
    if not previous_ids:
        return
    trained_users = {
        row.user_id
        for row in db.scalars(
            select(TrainingRecord).where(
                TrainingRecord.application_id == application.id, TrainingRecord.status == "completed"
            )
        )
    }
    assigned = {a.user_id for a in db.scalars(
        select(ApplicationUser).where(ApplicationUser.application_id == application.id))}
    already = {r.user_id for r in db.scalars(
        select(TrainingRecord).where(TrainingRecord.app_version_id == version.id))}
    for user_id in sorted((trained_users & assigned) - already):
        record = TrainingRecord(application_id=application.id, app_version_id=version.id,
                                user_id=user_id, status="required", required_at=utcnow())
        db.add(record)
        db.flush()
        audit.record(db, user, "create", "training_record", record.id,
                     f"{application.name} {version.version}",
                     new={"user_id": user_id, "status": "required", "reason": "new version released"})


def release_version(db: Session, user: User, password: str, version: AppVersion,
                    comment: str | None = None):
    """Release a version that is not part of a change request (for example the first validation)."""
    require_permission(user, "change.release")
    if version.status != "in_validation":
        raise Conflict("Only a version that is in validation can be released.")
    change = db.scalar(select(ChangeRequest).where(ChangeRequest.target_version_id == version.id))
    if change is not None and change.status != "cancelled":
        raise Conflict(f"This version belongs to change {change.code}. Release it from the change request.")
    application = db.get(Application, version.application_id)
    gate = evaluate_release_gate(db, version.id)
    if not gate.passed:
        failing = "; ".join(c.label for c in gate.failing())
        raise Conflict(f"The release gate is not open. Open items: {failing}.")
    signatures.forbid_same_person(user, version.created_by, "The person who prepared the version cannot release it.")
    signature = signatures.sign(
        db, user, password, meaning="Released", entity_type="app_version", entity_id=version.id,
        entity_label=f"{application.name} {version.version}",
        record_hash=canonical_hash({"version": version.version, "state": gate.state_hash}), comment=comment,
    )
    apply_release(db, user, version)
    return signature


def set_application_users(db: Session, user: User, application: Application, assignments: list[dict]) -> None:
    """Replace the list of people who use the application (access list)."""
    require_permission(user, "app.write")
    wanted = {a["user_id"]: a.get("app_role", "user") for a in assignments}
    for user_id in wanted:
        if db.get(User, user_id) is None:
            raise NotFound(f"User {user_id} was not found.")
    current = {
        row.user_id: row
        for row in db.scalars(select(ApplicationUser).where(ApplicationUser.application_id == application.id))
    }
    for user_id, row in current.items():
        if user_id not in wanted:
            db.delete(row)
            audit.record(db, user, "remove_user", "application", application.id, application.name,
                         old={"user_id": user_id, "app_role": row.app_role})
    for user_id, app_role in wanted.items():
        if user_id not in current:
            db.add(ApplicationUser(application_id=application.id, user_id=user_id, app_role=app_role))
            audit.record(db, user, "add_user", "application", application.id, application.name,
                         new={"user_id": user_id, "app_role": app_role})
        elif current[user_id].app_role != app_role:
            audit.record(db, user, "change_user_role", "application", application.id, application.name,
                         old={"user_id": user_id, "app_role": current[user_id].app_role},
                         new={"user_id": user_id, "app_role": app_role})
            current[user_id].app_role = app_role
    db.flush()
