from fastapi import APIRouter, Depends, File, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import schemas
from app.api.deps import current_user
from app.api.serializers import deviation_out, run_out, signature_out
from app.core.config import get_settings
from app.core.db import get_db
from app.models import AppVersion, Deviation, Evidence, TestCase, TestRun, User
from app.services import deviations, runs
from app.services.common import get_or_404

router = APIRouter(prefix="/api", tags=["execution"])


@router.get("/runs")
def list_runs(version_id: int | None = None, test_case_id: int | None = None, change_id: int | None = None,
              application_id: int | None = None, status: str | None = None, _: User = Depends(current_user),
              db: Session = Depends(get_db)):
    query = select(TestRun).order_by(TestRun.id.desc()).limit(300)
    if application_id:
        query = query.join(TestCase, TestCase.id == TestRun.test_case_id).where(
            TestCase.application_id == application_id)
    if version_id:
        query = query.where(TestRun.app_version_id == version_id)
    if test_case_id:
        query = query.where(TestRun.test_case_id == test_case_id)
    if change_id:
        query = query.where(TestRun.change_request_id == change_id)
    if status:
        query = query.where(TestRun.status == status)
    return [run_out(db, r) for r in db.scalars(query)]


@router.post("/runs", status_code=201)
def start_run(body: schemas.RunStart, user: User = Depends(current_user), db: Session = Depends(get_db)):
    run = runs.start_run(db, user, get_or_404(db, TestCase, body.test_case_id, "Test case"),
                         get_or_404(db, AppVersion, body.version_id, "Version"), body.change_request_id)
    db.commit()
    return run_out(db, run)


@router.get("/runs/{run_id}")
def get_run(run_id: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    return run_out(db, get_or_404(db, TestRun, run_id, "Run"))


@router.put("/runs/{run_id}/steps/{step_no}")
def record_step(run_id: int, step_no: int, body: schemas.StepResultIn, user: User = Depends(current_user),
                db: Session = Depends(get_db)):
    run = get_or_404(db, TestRun, run_id, "Run")
    runs.record_step(db, user, run, step_no, body.result, body.actual_result, body.comment)
    db.commit()
    return run_out(db, run)


@router.post("/runs/{run_id}/steps/{step_no}/evidence", status_code=201)
def upload_evidence(run_id: int, step_no: int, file: UploadFile = File(...), user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    run = get_or_404(db, TestRun, run_id, "Run")
    data = file.file.read(get_settings().max_evidence_bytes + 1)
    runs.add_evidence(db, user, run, step_no, file.filename or "evidence", file.content_type or "", data)
    db.commit()
    return run_out(db, run)


@router.get("/evidence/{evidence_id}")
def download_evidence(evidence_id: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    evidence = get_or_404(db, Evidence, evidence_id, "Evidence")
    return Response(
        evidence.data, media_type=evidence.content_type,
        headers={
            "Content-Disposition": f'inline; filename="{evidence.filename}"',
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox; default-src 'none'; img-src 'self' data:",
        },
    )


@router.post("/runs/{run_id}/complete")
def complete_run(run_id: int, body: schemas.SignatureIn, user: User = Depends(current_user),
                 db: Session = Depends(get_db)):
    run = get_or_404(db, TestRun, run_id, "Run")
    signature = runs.complete_run(db, user, body.password, run, body.comment)
    db.commit()
    return {"run": run_out(db, run), "signature": signature_out(signature)}


@router.post("/runs/{run_id}/review")
def review_run(run_id: int, body: schemas.SignatureIn, user: User = Depends(current_user),
               db: Session = Depends(get_db)):
    run = get_or_404(db, TestRun, run_id, "Run")
    signature = runs.review_run(db, user, body.password, run, body.comment)
    db.commit()
    return {"run": run_out(db, run), "signature": signature_out(signature)}


# ---------------------------------------------------------------- deviations

@router.get("/deviations")
def list_deviations(application_id: int | None = None, status: str | None = None,
                    _: User = Depends(current_user), db: Session = Depends(get_db)):
    query = select(Deviation).order_by(Deviation.id.desc())
    if application_id:
        query = query.where(Deviation.application_id == application_id)
    if status == "open":
        query = query.where(Deviation.status.in_(deviations.OPEN_STATUSES))
    elif status:
        query = query.where(Deviation.status == status)
    return [deviation_out(db, d) for d in db.scalars(query)]


@router.post("/deviations", status_code=201)
def create_deviation(body: schemas.DeviationCreate, user: User = Depends(current_user),
                     db: Session = Depends(get_db)):
    deviation = deviations.create_deviation(db, user, body.model_dump())
    db.commit()
    return deviation_out(db, deviation)


@router.get("/deviations/{deviation_id}")
def get_deviation(deviation_id: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    return deviation_out(db, get_or_404(db, Deviation, deviation_id, "Deviation"))


@router.patch("/deviations/{deviation_id}")
def update_deviation(deviation_id: int, body: schemas.DeviationUpdate, user: User = Depends(current_user),
                     db: Session = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    reason = data.pop("reason")
    deviation = deviations.update_deviation(db, user, get_or_404(db, Deviation, deviation_id, "Deviation"),
                                            data, reason)
    db.commit()
    return deviation_out(db, deviation)


@router.post("/deviations/{deviation_id}/resolve")
def resolve_deviation(deviation_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    deviation = deviations.resolve_deviation(db, user, get_or_404(db, Deviation, deviation_id, "Deviation"))
    db.commit()
    return deviation_out(db, deviation)


@router.post("/deviations/{deviation_id}/close")
def close_deviation(deviation_id: int, body: schemas.CloseIn, user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    deviation = get_or_404(db, Deviation, deviation_id, "Deviation")
    deviations.close_deviation(db, user, body.password, deviation, body.comment)
    db.commit()
    return deviation_out(db, deviation)


@router.post("/deviations/{deviation_id}/accept")
def accept_deviation(deviation_id: int, body: schemas.CloseIn, user: User = Depends(current_user),
                     db: Session = Depends(get_db)):
    deviation = get_or_404(db, Deviation, deviation_id, "Deviation")
    deviations.accept_deviation(db, user, body.password, deviation, body.comment)
    db.commit()
    return deviation_out(db, deviation)
