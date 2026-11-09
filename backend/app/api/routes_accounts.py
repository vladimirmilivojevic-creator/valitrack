from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import schemas
from app.api.deps import current_user, set_session_cookie
from app.api.serializers import signature_out, user_out
from app.core.db import get_db
from app.core.permissions import permissions_for
from app.core.security import COOKIE_NAME, create_session_token
from app.models import ESignature, User
from app.services import auth, users
from app.services.common import get_or_404

router = APIRouter(prefix="/api", tags=["accounts"])


@router.post("/auth/login")
def login(body: schemas.LoginIn, response: Response, db: Session = Depends(get_db)):
    user = auth.login(db, body.username, body.password)
    token, csrf = create_session_token(user.id)
    set_session_cookie(response, token)
    return {"user": user_out(user), "permissions": permissions_for(user.role), "csrf_token": csrf}


@router.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/auth/me")
def me(request: Request, user: User = Depends(current_user)):
    return {"user": user_out(user), "permissions": permissions_for(user.role),
            "csrf_token": request.state.csrf_token}


@router.post("/auth/change-password")
def change_password(body: schemas.PasswordChangeIn, user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    auth.change_password(db, user, body.current_password, body.new_password)
    return {"ok": True}


@router.get("/users")
def list_users(_: User = Depends(current_user), db: Session = Depends(get_db)):
    return [user_out(u) for u in db.scalars(select(User).order_by(User.full_name))]


@router.post("/users", status_code=201)
def create_user(body: schemas.UserCreate, admin: User = Depends(current_user), db: Session = Depends(get_db)):
    user = users.create_user(db, admin, body.model_dump())
    db.commit()
    return user_out(user)


@router.patch("/users/{user_id}")
def update_user(user_id: int, body: schemas.UserUpdate, admin: User = Depends(current_user),
                db: Session = Depends(get_db)):
    user = users.update_user(db, admin, get_or_404(db, User, user_id, "User"), body.model_dump(exclude_unset=True))
    db.commit()
    return user_out(user)


@router.post("/users/{user_id}/unlock")
def unlock_user(user_id: int, admin: User = Depends(current_user), db: Session = Depends(get_db)):
    users.unlock_user(db, admin, get_or_404(db, User, user_id, "User"))
    db.commit()
    return {"ok": True}


@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: int, body: schemas.PasswordResetIn, admin: User = Depends(current_user),
                   db: Session = Depends(get_db)):
    users.reset_password(db, admin, get_or_404(db, User, user_id, "User"), body.new_password)
    db.commit()
    return {"ok": True}


@router.get("/signatures")
def list_signatures(entity_type: str, entity_id: int, _: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    rows = db.scalars(select(ESignature).where(ESignature.entity_type == entity_type,
                                               ESignature.entity_id == entity_id).order_by(ESignature.id))
    return [signature_out(s) for s in rows]
