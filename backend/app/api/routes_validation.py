from fastapi import APIRouter, Depends, Response
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api import schemas
from app.api.deps import current_user
from app.api.serializers import (
    application_out,
    report_doc_out,
    requirement_out,
    signature_out,
    test_case_out,
    version_out,
)
from app.core.db import get_db
from app.models import Application, AppVersion, ReportDocument, Requirement, TestCase, User
from app.services import applications, report_docs, requirements, risk, testcases
from app.services.common import get_or_404, to_jsonable
from app.services.gate import evaluate_release_gate

router = APIRouter(prefix="/api", tags=["validation"])


# ---------------------------------------------------------------- applications and versions

@router.get("/applications")
def list_applications(_: User = Depends(current_user), db: Session = Depends(get_db)):
    return [application_out(db, a) for a in db.scalars(select(Application).order_by(Application.name))]


@router.post("/applications", status_code=201)
def create_application(body: schemas.ApplicationCreate, user: User = Depends(current_user),
                       db: Session = Depends(get_db)):
    data = body.model_dump()
    initial = data.pop("initial_version")
    application = applications.create_application(db, user, data, initial)
    db.commit()
    return application_out(db, application, detail=True)


@router.get("/applications/{application_id}")
def get_application(application_id: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    return application_out(db, get_or_404(db, Application, application_id, "Application"), detail=True)


@router.patch("/applications/{application_id}")
def update_application(application_id: int, body: schemas.ApplicationUpdate, user: User = Depends(current_user),
                       db: Session = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    reason = data.pop("reason")
    application = applications.update_application(
        db, user, get_or_404(db, Application, application_id, "Application"), data, reason)
    db.commit()
    return application_out(db, application, detail=True)


@router.post("/applications/{application_id}/versions", status_code=201)
def create_version(application_id: int, body: schemas.VersionCreate, user: User = Depends(current_user),
                   db: Session = Depends(get_db)):
    version = applications.create_version(
        db, user, get_or_404(db, Application, application_id, "Application"), body.version, body.release_notes)
    db.commit()
    return version_out(version)


@router.put("/applications/{application_id}/users")
def set_application_users(application_id: int, body: schemas.AppUsersIn, user: User = Depends(current_user),
                          db: Session = Depends(get_db)):
    application = get_or_404(db, Application, application_id, "Application")
    applications.set_application_users(db, user, application, [a.model_dump() for a in body.assignments])
    db.commit()
    return application_out(db, application, detail=True)


@router.get("/versions/{version_id}/gate")
def get_gate(version_id: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    gate = evaluate_release_gate(db, version_id)
    return {
        "version_id": version_id, "ready_for_report": gate.ready_for_report, "passed": gate.passed,
        "state_hash": gate.state_hash,
        "checks": [{"key": c.key, "label": c.label, "passed": c.passed, "detail": c.detail} for c in gate.checks],
    }


@router.post("/versions/{version_id}/approve-urs")
def approve_urs(version_id: int, body: schemas.SignatureIn, user: User = Depends(current_user),
                db: Session = Depends(get_db)):
    version = get_or_404(db, AppVersion, version_id, "Version")
    signature = applications.approve_urs(db, user, body.password, version, body.comment)
    db.commit()
    return {"version": version_out(version), "signature": signature_out(signature)}


@router.post("/versions/{version_id}/release")
def release_version(version_id: int, body: schemas.SignatureIn, user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    version = get_or_404(db, AppVersion, version_id, "Version")
    signature = applications.release_version(db, user, body.password, version, body.comment)
    db.commit()
    return {"version": version_out(version), "signature": signature_out(signature)}


# ---------------------------------------------------------------- report documents

@router.get("/versions/{version_id}/reports")
def list_reports(version_id: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(ReportDocument).where(ReportDocument.app_version_id == version_id)
                      .order_by(ReportDocument.id.desc()))
    return [report_doc_out(d) for d in rows]


@router.post("/versions/{version_id}/reports", status_code=201)
def generate_report(version_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    version = get_or_404(db, AppVersion, version_id, "Version")
    document = report_docs.generate_report(db, user, version)
    db.commit()
    return report_doc_out(document)


@router.get("/report-documents/{document_id}/pdf")
def download_report(document_id: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    document = get_or_404(db, ReportDocument, document_id, "Report")
    pdf = report_docs.download_pdf(db, document)
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{document.doc_number}.pdf"'})


@router.post("/report-documents/{document_id}/approve")
def approve_report(document_id: int, body: schemas.SignatureIn, user: User = Depends(current_user),
                   db: Session = Depends(get_db)):
    document = get_or_404(db, ReportDocument, document_id, "Report")
    signature = report_docs.approve_report(db, user, body.password, document, body.comment)
    db.commit()
    return {"report": report_doc_out(document), "signature": signature_out(signature)}


# ---------------------------------------------------------------- requirements and risk

@router.get("/risk/preview")
def risk_preview(severity: int, probability: int, detectability: int, _: User = Depends(current_user)):
    return {"rpn": risk.rpn(severity, probability, detectability),
            "risk_level": risk.risk_level(severity, probability, detectability)}


@router.get("/applications/{application_id}/requirements")
def list_requirements(application_id: int, include_retired: bool = False, _: User = Depends(current_user),
                      db: Session = Depends(get_db)):
    query = select(Requirement).where(Requirement.application_id == application_id).order_by(Requirement.code)
    if not include_retired:
        query = query.where(Requirement.status == "active")
    return [requirement_out(db, r) for r in db.scalars(query)]


@router.post("/applications/{application_id}/requirements", status_code=201)
def create_requirement(application_id: int, body: schemas.RequirementCreate, user: User = Depends(current_user),
                       db: Session = Depends(get_db)):
    application = get_or_404(db, Application, application_id, "Application")
    requirement = requirements.create_requirement(db, user, application, body.model_dump())
    db.commit()
    db.refresh(requirement)
    return requirement_out(db, requirement)


@router.patch("/requirements/{requirement_id}")
def update_requirement(requirement_id: int, body: schemas.RequirementUpdate, user: User = Depends(current_user),
                       db: Session = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    reason = data.pop("reason")
    requirement = requirements.update_requirement(
        db, user, get_or_404(db, Requirement, requirement_id, "Requirement"), data, reason)
    db.commit()
    return requirement_out(db, requirement)


@router.post("/requirements/{requirement_id}/retire")
def retire_requirement(requirement_id: int, body: schemas.ReasonIn, user: User = Depends(current_user),
                       db: Session = Depends(get_db)):
    requirement = requirements.retire_requirement(
        db, user, get_or_404(db, Requirement, requirement_id, "Requirement"), body.reason)
    db.commit()
    return requirement_out(db, requirement)


# ---------------------------------------------------------------- test cases

@router.get("/applications/{application_id}/test-cases")
def list_test_cases(application_id: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(TestCase).where(TestCase.application_id == application_id).order_by(TestCase.code))
    return [test_case_out(db, t) for t in rows]


@router.post("/applications/{application_id}/test-cases", status_code=201)
def create_test_case(application_id: int, body: schemas.TestCaseCreate, user: User = Depends(current_user),
                     db: Session = Depends(get_db)):
    application = get_or_404(db, Application, application_id, "Application")
    test_case = testcases.create_test_case(db, user, application, body.model_dump())
    db.commit()
    return test_case_out(db, test_case)


@router.get("/test-cases/{test_case_id}")
def get_test_case(test_case_id: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    return test_case_out(db, get_or_404(db, TestCase, test_case_id, "Test case"))


@router.patch("/test-cases/{test_case_id}")
def update_test_case(test_case_id: int, body: schemas.TestCaseUpdate, user: User = Depends(current_user),
                     db: Session = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    reason = data.pop("reason")
    test_case = testcases.update_test_case(db, user, get_or_404(db, TestCase, test_case_id, "Test case"), data, reason)
    db.commit()
    return test_case_out(db, test_case)


@router.put("/test-cases/{test_case_id}/requirements")
def set_links(test_case_id: int, body: schemas.LinksIn, user: User = Depends(current_user),
              db: Session = Depends(get_db)):
    test_case = get_or_404(db, TestCase, test_case_id, "Test case")
    testcases.set_requirement_links(db, user, test_case, body.requirement_ids)
    db.commit()
    return test_case_out(db, test_case)


@router.post("/test-cases/{test_case_id}/approve")
def approve_test_case(test_case_id: int, body: schemas.SignatureIn, user: User = Depends(current_user),
                      db: Session = Depends(get_db)):
    test_case = get_or_404(db, TestCase, test_case_id, "Test case")
    signature = testcases.approve_test_case(db, user, body.password, test_case, body.comment)
    db.commit()
    return {"test_case": test_case_out(db, test_case), "signature": signature_out(signature)}


@router.post("/test-cases/{test_case_id}/retire")
def retire_test_case(test_case_id: int, body: schemas.ReasonIn, user: User = Depends(current_user),
                     db: Session = Depends(get_db)):
    test_case = testcases.retire_test_case(db, user, get_or_404(db, TestCase, test_case_id, "Test case"), body.reason)
    db.commit()
    return test_case_out(db, test_case)


@router.get("/applications/{application_id}/traceability")
def traceability(application_id: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    result = db.execute(text(
        "SELECT * FROM vw_traceability WHERE application_id = :id ORDER BY requirement_code, test_code"),
        {"id": application_id})
    return [to_jsonable(dict(row)) for row in result.mappings()]
