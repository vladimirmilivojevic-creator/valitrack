from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import Forbidden, Invalid, Unauthorized
from app.core.security import hash_password, verify_password
from app.models import User
from app.services import audit
from app.services.common import utcnow


def check_password(db: Session, user: User, password: str, *, action: str) -> None:
    """Check a password for a login or for an electronic signature.

    Wrong passwords are counted. After too many in a row the account is locked for a while
    (21 CFR Part 11, 11.300(d): safeguards against unauthorised use of credentials).
    The failure is committed before the error is raised, otherwise the rollback would erase it.
    """
    settings = get_settings()
    now = utcnow()
    if user.locked_until and user.locked_until > now:
        raise Forbidden("This account is locked for a short time after too many wrong passwords.")
    if verify_password(user.password_hash, password):
        user.failed_logins = 0
        return
    user.failed_logins += 1
    audit.record(db, user, "password_failed", "user", user.id, user.username, reason=action)
    if user.failed_logins >= settings.lockout_threshold:
        user.locked_until = now + timedelta(minutes=settings.effective_lockout_minutes)
        user.failed_logins = 0
        audit.record(db, user, "account_locked", "user", user.id, user.username)
    db.commit()
    raise Forbidden("The password is not correct.")


def login(db: Session, username: str, password: str) -> User:
    user = db.scalar(select(User).where(User.username == username.strip().lower()))
    if user is None or not user.is_active:
        raise Unauthorized("Username or password is not correct.")
    try:
        check_password(db, user, password, action="login")
    except Forbidden as error:
        if "locked" in error.message:
            raise
        raise Unauthorized("Username or password is not correct.") from None
    user.last_login_at = utcnow()
    audit.record(db, user, "login", "user", user.id, user.username)
    db.commit()
    return user


def validate_new_password(password: str) -> None:
    if len(password) < 10 or password.isalpha() or password.isdigit():
        raise Invalid("The password needs at least 10 characters, with letters and digits.")


def change_password(db: Session, user: User, current: str, new: str) -> None:
    check_password(db, user, current, action="password change")
    validate_new_password(new)
    user.password_hash = hash_password(new)
    audit.record(db, user, "password_changed", "user", user.id, user.username)
    db.commit()
