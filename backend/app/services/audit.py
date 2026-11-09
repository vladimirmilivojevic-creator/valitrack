"""Audit trail writer.

Services call record() whenever something changes. The entries wait in the session
and are written in the same database transaction just before it commits, so a change
and its audit entry always succeed or fail together. The database trigger then adds
the time, the sequence number and the hash chain.
"""

import json
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.orm import Session

from app.models import User
from app.services.common import to_jsonable

_INSERT = text(
    """
    INSERT INTO audit_log (actor_id, actor_name, action, entity_type, entity_id,
                           entity_label, old_values, new_values, reason)
    VALUES (:actor_id, :actor_name, :action, :entity_type, :entity_id,
            :entity_label, CAST(:old_values AS jsonb), CAST(:new_values AS jsonb), :reason)
    """
)


def record(
    db: Session,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: int | str,
    label: str | None = None,
    old: dict[str, Any] | None = None,
    new: dict[str, Any] | None = None,
    reason: str | None = None,
) -> None:
    db.info.setdefault("audit_queue", []).append(
        {
            "actor_id": actor.id if actor else None,
            "actor_name": actor.full_name if actor else "System",
            "action": action,
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "entity_label": label,
            "old_values": json.dumps(to_jsonable(old)) if old is not None else None,
            "new_values": json.dumps(to_jsonable(new)) if new is not None else None,
            "reason": reason,
        }
    )


def changed_fields(before: dict[str, Any], after: dict[str, Any]) -> tuple[dict, dict]:
    """Only the fields that differ, so the audit entry shows exactly what changed."""
    old = {k: v for k, v in before.items() if after.get(k) != v}
    new = {k: after[k] for k in old}
    return old, new


@event.listens_for(Session, "before_commit")
def _write_queued_entries(session: Session) -> None:
    queue = session.info.pop("audit_queue", None)
    for entry in queue or []:
        session.execute(_INSERT, entry)


@event.listens_for(Session, "after_rollback")
def _drop_queued_entries(session: Session) -> None:
    session.info.pop("audit_queue", None)
