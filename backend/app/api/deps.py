from datetime import UTC, datetime

from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import Forbidden, Unauthorized
from app.core.security import COOKIE_NAME, create_session_token, decode_session_token
from app.models import User

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
REFRESH_AFTER_SECONDS = 300


def set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        COOKIE_NAME, token, max_age=settings.session_minutes * 60, httponly=True,
        secure=settings.cookie_secure, samesite="lax", path="/",
    )


def current_user(request: Request, response: Response, db: Session = Depends(get_db)) -> User:
    """The signed-in user. Changing requests must also carry the CSRF token of the session."""
    token = request.cookies.get(COOKIE_NAME)
    payload = decode_session_token(token) if token else None
    if payload is None:
        raise Unauthorized("Please sign in.")
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise Unauthorized("Please sign in.")
    if request.method not in SAFE_METHODS and request.headers.get("X-CSRF-Token") != payload["csrf"]:
        raise Forbidden("The security token of your session is missing or wrong. Reload the page.")
    request.state.csrf_token = payload["csrf"]
    # Sliding session: an active user stays signed in, an idle one is signed out after 30 minutes.
    if datetime.now(UTC).timestamp() - payload["iat"] > REFRESH_AFTER_SECONDS:
        fresh, _ = create_session_token(user.id, payload["csrf"])
        set_session_cookie(response, fresh)
    return user
