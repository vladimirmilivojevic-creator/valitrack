"""Small helpers shared by the services."""

import hashlib
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import Forbidden, Invalid, NotFound
from app.core.permissions import has_permission
from app.models import User


def utcnow() -> datetime:
    return datetime.now(UTC)


def to_jsonable(value: Any) -> Any:
    """Turn values into something json.dumps accepts (dates, decimals, nested dicts)."""
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple | set):
        return [to_jsonable(v) for v in value]
    return value


def canonical_hash(value: Any) -> str:
    """SHA-256 of a value in a fixed JSON form. The same content always gives the same hash."""
    text = json.dumps(to_jsonable(value), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def row_dict(obj: Any, exclude: tuple[str, ...] = ()) -> dict[str, Any]:
    """Column values of an ORM object as a plain dict (binary and secret columns are left out)."""
    skip = {"password_hash", "data", "pdf", *exclude}
    return {
        c.key: to_jsonable(getattr(obj, c.key))
        for c in obj.__table__.columns
        if c.key not in skip
    }


def get_or_404(db: Session, model: type, object_id: int, label: str | None = None):
    obj = db.get(model, object_id)
    if obj is None:
        raise NotFound(f"{label or model.__name__} {object_id} was not found.")
    return obj


def require_permission(user: User, permission: str) -> None:
    if not has_permission(user.role, permission):
        raise Forbidden("Your role is not allowed to do this.")


def require_text(value: str | None, field: str, min_length: int = 3) -> str:
    text = (value or "").strip()
    if len(text) < min_length:
        raise Invalid(f"{field} is required.")
    return text
