from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import schemas
from app.api.deps import current_user
from app.api.serializers import change_out, signature_out
from app.core.db import get_db
from app.models import Application, ChangeRequest, User
from app.services import changes
from app.services.common import get_or_404

router = APIRouter(prefix="/api/changes", tags=["change control"])


def _load(db: Session, change_id: int) -> ChangeRequest:
    return get_or_404(db, ChangeRequest, change_id, "Change request")


@router.get("")
def list_changes(application_id: int | None = None, status: str | None = None, open_only: bool = False,
                 _: User = Depends(current_user), db: Session = Depends(get_db)):
    query = select(ChangeRequest).order_by(ChangeRequest.id.desc())
    if application_id:
        query = query.where(ChangeRequest.application_id == application_id)
    if status:
        query = query.where(ChangeRequest.status == status)
    if open_only:
        query = query.where(ChangeRequest.status.in_(changes.OPEN_STATUSES))
    return [change_out(db, c) for c in db.scalars(query)]


@router.post("", status_code=201)
def create_change(body: schemas.ChangeCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    data = body.model_dump()
    application = get_or_404(db, Application, data.pop("application_id"), "Application")
    change = changes.create_change(db, user, application, data)
    db.commit()
    return change_out(db, change, detail=True)


@router.get("/{change_id}")
def get_change(change_id: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    return change_out(db, _load(db, change_id), detail=True)


@router.patch("/{change_id}")
def update_change(change_id: int, body: schemas.ChangeUpdate, user: User = Depends(current_user),
                  db: Session = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    reason = data.pop("reason")
    change = changes.update_change(db, user, _load(db, change_id), data, reason)
    db.commit()
    return change_out(db, change, detail=True)


@router.post("/{change_id}/submit")
def submit(change_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    change = changes.submit(db, user, _load(db, change_id))
    db.commit()
    return change_out(db, change, detail=True)


@router.post("/{change_id}/start-assessment")
def start_assessment(change_id: int, body: schemas.AssessmentStartIn, user: User = Depends(current_user),
                     db: Session = Depends(get_db)):
    change = changes.start_assessment(db, user, _load(db, change_id), body.departments)
    db.commit()
    return change_out(db, change, detail=True)


@router.put("/{change_id}/impacts/{department}")
def assess(change_id: int, department: str, body: schemas.ImpactIn, user: User = Depends(current_user),
           db: Session = Depends(get_db)):
    change = _load(db, change_id)
    changes.assess(db, user, change, department, body.impact_level, body.affects_validated_state, body.comment)
    db.commit()
    return change_out(db, change, detail=True)


@router.post("/{change_id}/approve")
def approve(change_id: int, body: schemas.SignatureIn, user: User = Depends(current_user),
            db: Session = Depends(get_db)):
    change = _load(db, change_id)
    signature = changes.approve(db, user, body.password, change, body.comment)
    db.commit()
    return {"change": change_out(db, change, detail=True), "signature": signature_out(signature)}


@router.post("/{change_id}/reject")
def reject(change_id: int, body: schemas.RejectIn, user: User = Depends(current_user),
           db: Session = Depends(get_db)):
    change = _load(db, change_id)
    signature = changes.reject(db, user, body.password, change, body.reason)
    db.commit()
    return {"change": change_out(db, change, detail=True), "signature": signature_out(signature)}


@router.post("/{change_id}/start-testing")
def start_testing(change_id: int, body: schemas.TestingStartIn, user: User = Depends(current_user),
                  db: Session = Depends(get_db)):
    change = _load(db, change_id)
    changes.start_testing(db, user, change, body.test_case_ids)
    db.commit()
    return change_out(db, change, detail=True)


@router.post("/{change_id}/complete-testing")
def complete_testing(change_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    change = _load(db, change_id)
    changes.complete_testing(db, user, change)
    db.commit()
    return change_out(db, change, detail=True)


@router.post("/{change_id}/release")
def release(change_id: int, body: schemas.SignatureIn, user: User = Depends(current_user),
            db: Session = Depends(get_db)):
    change = _load(db, change_id)
    signature = changes.release(db, user, body.password, change, body.comment)
    db.commit()
    return {"change": change_out(db, change, detail=True), "signature": signature_out(signature)}


@router.post("/{change_id}/cancel")
def cancel(change_id: int, body: schemas.ReasonIn, user: User = Depends(current_user),
           db: Session = Depends(get_db)):
    change = _load(db, change_id)
    changes.cancel(db, user, change, body.reason)
    db.commit()
    return change_out(db, change, detail=True)
