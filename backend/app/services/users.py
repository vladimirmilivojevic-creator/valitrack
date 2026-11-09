"""User administration."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import Conflict, Invalid
from app.core.permissions import DEPARTMENTS, ROLES
from app.core.security import hash_password
from app.models import User
from app.services import audit
from app.services.auth import validate_new_password
from app.services.common import require_permission, require_text, row_dict


def _check(role: str | None, department: str | None) -> None:
    if role is not None and role not in ROLES:
        raise Invalid("Unknown role.")
    if department is not None and department not in DEPARTMENTS:
        raise Invalid("Unknown department.")


def create_user(db: Session, admin: User, data: dict) -> User:
    require_permission(admin, "user.manage")
    _check(data.get("role"), data.get("department"))
    username = require_text(data.get("username"), "The user name", 3).lower()
    if db.scalar(select(User).where(User.username == username)):
        raise Conflict("This user name is already taken.")
    validate_new_password(data["password"])
    user = User(
        username=username, full_name=require_text(data.get("full_name"), "The name"),
        email=require_text(data.get("email"), "The email", 5), role=data["role"],
        department=data["department"], password_hash=hash_password(data["password"]),
    )
    db.add(user)
    db.flush()
    audit.record(db, admin, "create", "user", user.id, user.username, new=row_dict(user))
    return user


def update_user(db: Session, admin: User, user: User, data: dict) -> User:
    require_permission(admin, "user.manage")
    _check(data.get("role"), data.get("department"))
    if data.get("is_active") is False and user.id == admin.id:
        raise Conflict("You cannot deactivate your own account.")
    before = row_dict(user)
    for key in ("full_name", "email", "role", "department", "is_active"):
        if key in data:
            setattr(user, key, data[key])
    db.flush()
    old, new = audit.changed_fields(before, row_dict(user))
    if new:
        audit.record(db, admin, "update", "user", user.id, user.username, old, new)
    return user


def unlock_user(db: Session, admin: User, user: User) -> None:
    require_permission(admin, "user.manage")
    user.failed_logins = 0
    user.locked_until = None
    db.flush()
    audit.record(db, admin, "unlock", "user", user.id, user.username)


def reset_password(db: Session, admin: User, user: User, new_password: str) -> None:
    require_permission(admin, "user.manage")
    validate_new_password(new_password)
    user.password_hash = hash_password(new_password)
    user.failed_logins = 0
    user.locked_until = None
    db.flush()
    audit.record(db, admin, "reset_password", "user", user.id, user.username)
