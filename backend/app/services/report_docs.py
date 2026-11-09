"""Validation summary report documents: generate, approve, download."""

import hashlib

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.errors import Conflict
from app.models import (
    Application,
    AppVersion,
    ChangeRequest,
    ESignature,
    ReportDocument,
    TestRun,
    User,
)
from app.reports.pdf import append_page, build_approval_page, build_report_pdf
from app.services import audit, signatures
from app.services.common import require_permission, utcnow
from app.services.gamp import GAMP_CATEGORIES, validation_approach
from app.services.gate import GateResult, evaluate_release_gate

RESULT_TEXT = {"passed": "Passed", "failed": "FAILED", "blocked": "Blocked", None: "Not run"}


def _stamp(value) -> str:
    return value.strftime("%Y-%m-%d %H:%M") if value else ""


def _user_names(db: Session) -> dict[int, str]:
    return {u.id: u.full_name for u in db.scalars(select(User))}


def collect_report_data(db: Session, version: AppVersion, gate: GateResult, generated_by: User,
                        doc_number: str) -> dict:
    facts = gate.facts
    application: Application = facts["application"]
    names = _user_names(db)
    change = db.scalar(select(ChangeRequest).where(ChangeRequest.target_version_id == version.id))
    tests_of = facts["tests_of_requirement"]
    latest = facts["latest_run"]

    requirements = [{
        "code": r.code, "kind": r.kind, "title": r.title, "severity": r.severity or "-",
        "probability": r.probability or "-", "detectability": r.detectability or "-",
        "rpn": r.rpn if r.rpn is not None else "-", "risk_level": r.risk_level,
        "tests": ", ".join(t.code for t in tests_of[r.id]),
    } for r in facts["requirements"]]

    tested = {t.id: t for tests in tests_of.values() for t in tests}
    tests = []
    for test in sorted(tested.values(), key=lambda t: t.code):
        run: TestRun | None = latest.get(test.id)
        tests.append({
            "code": test.code, "test_type": test.test_type, "title": test.title,
            "result_text": RESULT_TEXT[run.result if run else None],
            "executed_by": names.get(run.executed_by) if run else None,
            "completed_at": _stamp(run.completed_at) if run else None,
            "reviewed_by": names.get(run.reviewed_by) if run and run.reviewed_by else None,
        })
    results = [latest[i].result if i in latest else None for i in tested]
    uncovered = [r for r in facts["requirements"] if not tests_of[r.id]]
    totals = {
        "tests": len(tested), "passed": results.count("passed"), "failed": results.count("failed"),
        "blocked": results.count("blocked"), "not_run": results.count(None),
        "requirements": len(facts["requirements"]), "covered": len(facts["requirements"]) - len(uncovered),
    }

    deviations = [{
        "code": d.code, "title": d.title, "severity": d.severity, "status": d.status.replace("_", " "),
        "root_cause": d.root_cause, "corrective_action": d.corrective_action,
    } for d in sorted(facts["deviations"], key=lambda d: d.code)]

    chain = db.execute(text("SELECT entries, first_broken_seq, head_hash FROM verify_audit_chain()")).one()

    if gate.passed:
        conclusion = (f"Conclusion: {application.name} {version.version} is validated for its intended use. "
                      "All release gate checks are met.")
    elif gate.ready_for_report:
        conclusion = ("Conclusion: testing is complete and all checks except the approval of this report are met. "
                      "The version can be released after QA approves this report.")
    else:
        open_items = ", ".join(c.label for c in gate.failing())
        conclusion = f"Conclusion: the version is NOT ready for release. Open items: {open_items}."

    return {
        "doc_number": doc_number,
        "generated_at": _stamp(utcnow()) + " UTC",
        "generated_by": generated_by.full_name,
        "state_hash": gate.state_hash,
        "gate_ready": gate.ready_for_report,
        "application": {
            "code": application.code, "name": application.name, "vendor": application.vendor,
            "department": application.department, "owner": names.get(application.owner_id, ""),
            "gamp_category": application.gamp_category, "gamp_name": GAMP_CATEGORIES[application.gamp_category]["name"],
            "risk_class": application.risk_class, "intended_use": application.intended_use,
            "approach": validation_approach(application.gamp_category, application.risk_class),
        },
        "version": {
            "version": version.version, "status": version.status,
            "change": ({"code": change.code, "title": change.title, "type": change.change_type,
                        "risk_level": change.risk_level} if change else None),
        },
        "requirements": requirements,
        "tests": tests,
        "totals": totals,
        "deviations": deviations,
        "gate": [{"passed": c.passed, "label": c.label, "detail": c.detail} for c in gate.checks],
        "conclusion": conclusion,
        "signatures": _signature_register(db, version, tested, facts, change),
        "audit": {"entries": chain.entries, "head_hash": chain.head_hash, "intact": chain.first_broken_seq is None},
    }


def _signature_register(db: Session, version: AppVersion, tested: dict, facts: dict, change) -> list[dict]:
    keys = [("requirements_baseline", version.id)]
    keys += [("test_case", t.id) for t in tested.values()]
    run_ids = [r.id for r in db.scalars(select(TestRun).where(TestRun.app_version_id == version.id))]
    keys += [("test_run", i) for i in run_ids]
    keys += [("deviation", d.id) for d in facts["deviations"]]
    if change:
        keys.append(("change_request", change.id))
    rows = []
    for entity_type, entity_id in keys:
        rows += signatures.signatures_for(db, entity_type, entity_id)
    rows.sort(key=lambda s: s.id)
    return [{
        "when": _stamp(s.signed_at), "who": s.signer_name, "role": s.signer_role.replace("_", " "),
        "meaning": s.meaning, "record": s.entity_label, "hash": s.signature_hash[:16],
    } for s in rows]


def generate_report(db: Session, user: User, version: AppVersion) -> ReportDocument:
    require_permission(user, "report.generate")
    gate = evaluate_release_gate(db, version.id)
    doc_number = db.scalar(text("SELECT 'VSR-' || lpad(nextval('report_code_seq')::text, 4, '0')"))
    data = collect_report_data(db, version, gate, user, doc_number)
    pdf = build_report_pdf(data)
    for older in db.scalars(select(ReportDocument).where(
            ReportDocument.app_version_id == version.id, ReportDocument.status == "draft")):
        older.status = "superseded"
    document = ReportDocument(
        doc_number=doc_number, app_version_id=version.id, generated_by=user.id, state_hash=gate.state_hash,
        sha256=hashlib.sha256(pdf).hexdigest(), gate_passed=gate.ready_for_report, pdf=pdf,
    )
    db.add(document)
    db.flush()
    audit.record(db, user, "generate", "report_document", document.id, doc_number,
                 new={"version_id": version.id, "sha256": document.sha256, "gate_ready": gate.ready_for_report})
    return document


def approve_report(db: Session, user: User, password: str, document: ReportDocument, comment: str | None = None):
    require_permission(user, "report.approve")
    if document.status != "draft":
        raise Conflict("Only the latest draft of a report can be approved.")
    version = db.get(AppVersion, document.app_version_id)
    gate = evaluate_release_gate(db, version.id)
    if not gate.ready_for_report:
        raise Conflict("The report cannot be approved while the release gate still has open items: "
                       + "; ".join(c.label for c in gate.failing() if c.key != "report_approved") + ".")
    if gate.state_hash != document.state_hash:
        raise Conflict("The report is out of date: results changed after it was generated. Generate it again.")
    signatures.forbid_same_person(user, document.generated_by, "The person who generated the report cannot approve it.")
    signature = signatures.sign(
        db, user, password, meaning="Approved", entity_type="report_document", entity_id=document.id,
        entity_label=document.doc_number, record_hash=document.sha256, comment=comment,
    )
    for other in db.scalars(select(ReportDocument).where(
            ReportDocument.app_version_id == version.id, ReportDocument.status == "approved")):
        other.status = "superseded"
    document.status = "approved"
    db.flush()
    audit.record(db, user, "approve", "report_document", document.id, document.doc_number,
                 old={"status": "draft"}, new={"status": "approved"})
    return signature


def download_pdf(db: Session, document: ReportDocument) -> bytes:
    """Approved reports are returned with an approval page added at the end."""
    if document.status != "approved":
        return document.pdf
    signature = db.scalar(select(ESignature).where(
        ESignature.entity_type == "report_document", ESignature.entity_id == document.id,
    ).order_by(ESignature.id.desc()))
    if signature is None:
        return document.pdf
    page = build_approval_page({
        "doc_number": document.doc_number, "signer": signature.signer_name,
        "role": signature.signer_role.replace("_", " "), "meaning": signature.meaning,
        "signed_at": signature.signed_at.strftime("%Y-%m-%d %H:%M:%S") + " UTC",
        "comment": signature.comment, "signature_hash": signature.signature_hash,
        "document_hash": document.sha256,
    })
    return append_page(document.pdf, page)
