"""Configuration baseline of an application.

While an application has a validated version, its configuration is part of the validated
state. Changing it needs an approved change request, so no one can "just tweak a setting".
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import Conflict
from app.models import Application, AppVersion, ChangeRequest, ConfigItem, User
from app.services import audit
from app.services.common import require_permission, require_text, row_dict

ALLOWED_CHANGE_STATUSES = ("approved", "testing", "ready_for_release")


def _require_change_control(db: Session, application: Application, change_request_id: int | None) -> int | None:
    live = db.scalar(select(AppVersion).where(AppVersion.application_id == application.id,
                                              AppVersion.status == "validated"))
    if live is None:
        return change_request_id  # not validated yet: free to configure
    change = db.get(ChangeRequest, change_request_id) if change_request_id else None
    if change is None or change.application_id != application.id or change.status not in ALLOWED_CHANGE_STATUSES:
        raise Conflict(
            f"{application.name} has a validated version. A configuration change needs an approved "
            "change request for this application (status approved, testing or ready for release)."
        )
    return change.id


def create_item(db: Session, user: User, application: Application, data: dict) -> ConfigItem:
    require_permission(user, "config.write")
    change_id = _require_change_control(db, application, data.get("change_request_id"))
    name = require_text(data.get("name"), "The setting name", 2)
    if db.scalar(select(ConfigItem).where(ConfigItem.application_id == application.id, ConfigItem.name == name)):
        raise Conflict("This setting already exists.")
    item = ConfigItem(application_id=application.id, name=name, value=require_text(data.get("value"), "The value", 1),
                      description=data.get("description"), last_change_request_id=change_id, updated_by=user.id)
    db.add(item)
    db.flush()
    audit.record(db, user, "create", "config_item", item.id, f"{application.name} / {item.name}", new=row_dict(item))
    return item


def update_item(db: Session, user: User, item: ConfigItem, data: dict, reason: str) -> ConfigItem:
    require_permission(user, "config.write")
    reason = require_text(reason, "A reason for the change")
    application = db.get(Application, item.application_id)
    change_id = _require_change_control(db, application, data.get("change_request_id"))
    before = row_dict(item)
    for key in ("value", "description"):
        if key in data:
            setattr(item, key, data[key])
    item.last_change_request_id = change_id or item.last_change_request_id
    item.updated_by = user.id
    db.flush()
    old, new = audit.changed_fields(before, row_dict(item))
    if new:
        audit.record(db, user, "update", "config_item", item.id, f"{application.name} / {item.name}",
                     old, new, reason)
    return item


def delete_item(db: Session, user: User, item: ConfigItem, reason: str, change_request_id: int | None) -> None:
    require_permission(user, "config.write")
    reason = require_text(reason, "A reason for removing the setting")
    application = db.get(Application, item.application_id)
    _require_change_control(db, application, change_request_id)
    audit.record(db, user, "delete", "config_item", item.id, f"{application.name} / {item.name}",
                 old=row_dict(item), reason=reason)
    db.delete(item)
    db.flush()
