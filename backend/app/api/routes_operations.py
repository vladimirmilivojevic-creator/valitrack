from fastapi import APIRouter, Depends
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api import schemas
from app.api.deps import current_user
from app.api.serializers import config_out, session_out, signature_out, ticket_out
from app.core.db import get_db
from app.models import Application, ConfigItem, SupportTicket, TrainingSession, User
from app.services import configuration, support, training
from app.services.common import get_or_404, to_jsonable

router = APIRouter(prefix="/api", tags=["operations"])


# ---------------------------------------------------------------- configuration baseline

@router.get("/applications/{application_id}/config")
def list_config(application_id: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(ConfigItem).where(ConfigItem.application_id == application_id)
                      .order_by(ConfigItem.name))
    return [config_out(i) for i in rows]


@router.post("/applications/{application_id}/config", status_code=201)
def create_config(application_id: int, body: schemas.ConfigCreate, user: User = Depends(current_user),
                  db: Session = Depends(get_db)):
    application = get_or_404(db, Application, application_id, "Application")
    item = configuration.create_item(db, user, application, body.model_dump())
    db.commit()
    return config_out(item)


@router.patch("/config/{item_id}")
def update_config(item_id: int, body: schemas.ConfigUpdate, user: User = Depends(current_user),
                  db: Session = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    reason = data.pop("reason")
    item = configuration.update_item(db, user, get_or_404(db, ConfigItem, item_id, "Setting"), data, reason)
    db.commit()
    return config_out(item)


@router.delete("/config/{item_id}")
def delete_config(item_id: int, reason: str, change_request_id: int | None = None,
                  user: User = Depends(current_user), db: Session = Depends(get_db)):
    configuration.delete_item(db, user, get_or_404(db, ConfigItem, item_id, "Setting"), reason, change_request_id)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- training

@router.get("/training/sessions")
def list_sessions(application_id: int | None = None, _: User = Depends(current_user),
                  db: Session = Depends(get_db)):
    query = select(TrainingSession).order_by(TrainingSession.session_date.desc(), TrainingSession.id.desc())
    if application_id:
        query = query.where(TrainingSession.application_id == application_id)
    return [session_out(db, s) for s in db.scalars(query)]


@router.post("/training/sessions", status_code=201)
def create_session(body: schemas.TrainingCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    data = body.model_dump()
    application = get_or_404(db, Application, data["application_id"], "Application")
    session = training.create_session(db, user, application, data)
    db.commit()
    return session_out(db, session)


@router.post("/training/sessions/{session_id}/complete")
def complete_session(session_id: int, body: schemas.TrainingComplete, user: User = Depends(current_user),
                     db: Session = Depends(get_db)):
    session = get_or_404(db, TrainingSession, session_id, "Training session")
    signature = training.complete_session(db, user, body.password, session, body.attended_ids)
    db.commit()
    return {"session": session_out(db, session), "signature": signature_out(signature)}


@router.post("/training/sessions/{session_id}/cancel")
def cancel_session(session_id: int, body: schemas.ReasonIn, user: User = Depends(current_user),
                   db: Session = Depends(get_db)):
    session = get_or_404(db, TrainingSession, session_id, "Training session")
    training.cancel_session(db, user, session, body.reason)
    db.commit()
    return session_out(db, session)


@router.get("/training/matrix")
def training_matrix(_: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(text("SELECT * FROM vw_training_compliance ORDER BY application_name, full_name")).mappings()
    return [to_jsonable(dict(r)) for r in rows]


# ---------------------------------------------------------------- support tickets

@router.get("/tickets")
def list_tickets(application_id: int | None = None, status: str | None = None, open_only: bool = False,
                 _: User = Depends(current_user), db: Session = Depends(get_db)):
    query = select(SupportTicket).order_by(SupportTicket.id.desc())
    if application_id:
        query = query.where(SupportTicket.application_id == application_id)
    if status:
        query = query.where(SupportTicket.status == status)
    if open_only:
        query = query.where(SupportTicket.status.in_(["open", "in_progress", "waiting_user"]))
    return [ticket_out(t) for t in db.scalars(query)]


@router.post("/tickets", status_code=201)
def create_ticket(body: schemas.TicketCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ticket = support.create_ticket(db, user, body.model_dump())
    db.commit()
    return ticket_out(ticket)


@router.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    return ticket_out(get_or_404(db, SupportTicket, ticket_id, "Ticket"))


@router.patch("/tickets/{ticket_id}")
def update_ticket(ticket_id: int, body: schemas.TicketUpdate, user: User = Depends(current_user),
                  db: Session = Depends(get_db)):
    ticket = support.update_ticket(db, user, get_or_404(db, SupportTicket, ticket_id, "Ticket"),
                                   body.model_dump(exclude_unset=True))
    db.commit()
    return ticket_out(ticket)


@router.post("/tickets/{ticket_id}/comments", status_code=201)
def add_comment(ticket_id: int, body: schemas.CommentIn, user: User = Depends(current_user),
                db: Session = Depends(get_db)):
    ticket = get_or_404(db, SupportTicket, ticket_id, "Ticket")
    support.add_comment(db, user, ticket, body.body)
    db.commit()
    db.refresh(ticket)
    return ticket_out(ticket)
