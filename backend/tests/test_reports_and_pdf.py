import hashlib
import io

import pytest
from pypdf import PdfReader

from app.models import ReportDocument
from app.reports.pdf import append_page, build_approval_page, build_report_pdf
from app.services import report_docs, reports
from conftest import PASSWORD
from helpers import approve_all, approve_report, execute_all, full_setup, validate


def pdf_text(data: bytes) -> str:
    return "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(data)).pages)


def sample_data(**overrides):
    data = {
        "doc_number": "VSR-0001", "generated_at": "2026-11-09 10:00 UTC", "generated_by": "Sophie Gruber",
        "state_hash": "a" * 64, "gate_ready": True,
        "application": {"code": "APP-001", "name": "Sample App", "vendor": "Vendor", "department": "QA",
                        "owner": "Nina Haas", "gamp_category": 4, "gamp_name": "Configured product",
                        "risk_class": "high", "intended_use": "Testing", "approach": "GAMP category 4. Test it."},
        "version": {"version": "1.0", "status": "in_validation", "change": None},
        "requirements": [{"code": "URS-001", "kind": "URS", "title": "It works", "severity": 3, "probability": 2,
                          "detectability": 2, "rpn": 12, "risk_level": "high", "tests": "TC-001"}],
        "tests": [{"code": "TC-001", "test_type": "OQ", "title": "Works", "result_text": "Passed",
                   "executed_by": "Lukas", "completed_at": "2026-11-09 09:00", "reviewed_by": "Eva"}],
        "totals": {"tests": 1, "passed": 1, "failed": 0, "blocked": 0, "not_run": 0, "requirements": 1, "covered": 1},
        "deviations": [],
        "gate": [{"passed": True, "label": "Requirements approved", "detail": "1 requirements approved."}],
        "conclusion": "Conclusion: ready.", "signatures": [],
        "audit": {"entries": 5, "head_hash": "b" * 64, "intact": True},
    }
    data.update(overrides)
    return data


def test_pdf_renders_a_complete_report():
    pdf = build_report_pdf(sample_data())
    text = pdf_text(pdf)
    assert pdf.startswith(b"%PDF")
    for needle in ("Validation Summary Report", "Sample App", "URS-001", "Release gate", "Audit trail integrity",
                   "VSR-0001", "Electronic signature register"):
        assert needle in text


def test_pdf_handles_special_characters_and_long_text():
    data = sample_data()
    data["requirements"][0]["title"] = "Tom & Jerry <script> \"quoted\" " + "long " * 80
    data["deviations"] = [{"code": "DEV-0001", "title": "Failed <b>", "severity": "major", "status": "open",
                           "root_cause": None, "corrective_action": None}]
    assert pdf_text(build_report_pdf(data)).count("DEV-0001") >= 1


def test_pdf_shows_open_gate_items_in_a_draft():
    data = sample_data(gate_ready=False, gate=[{"passed": False, "label": "Coverage", "detail": "2 missing"}])
    assert "NOT open" in pdf_text(build_report_pdf(data))


def test_approval_page_is_appended():
    report = build_report_pdf(sample_data())
    page = build_approval_page({"doc_number": "VSR-0001", "signer": "Eva Mayr", "role": "qa manager",
                                "meaning": "Approved", "signed_at": "2026-11-09 11:00:00 UTC", "comment": None,
                                "signature_hash": "c" * 64, "document_hash": "d" * 64})
    merged = append_page(report, page)
    assert len(PdfReader(io.BytesIO(merged)).pages) == len(PdfReader(io.BytesIO(report)).pages) + 1
    assert "Approval record" in pdf_text(merged) and "Eva Mayr" in pdf_text(merged)


def test_generated_report_contains_the_real_data(db, people):
    setup = full_setup(db, people, name="Report App")
    approve_all(db, people, setup)
    execute_all(db, people, setup)
    document = report_docs.generate_report(db, people.ve, setup.version)
    db.commit()
    stored = db.get(ReportDocument, document.id)
    assert stored.sha256 == hashlib.sha256(stored.pdf).hexdigest()
    text = pdf_text(stored.pdf)
    assert "Report App" in text and "URS-001" in text and "TC-002" in text
    assert "Approved" in text  # the signature register lists the QA approvals
    assert stored.gate_passed is True and stored.status == "draft"


def test_generating_again_supersedes_the_older_draft(db, people):
    setup = full_setup(db, people)
    approve_all(db, people, setup)
    first = report_docs.generate_report(db, people.ve, setup.version)
    second = report_docs.generate_report(db, people.ve, setup.version)
    db.commit()
    assert first.status == "superseded" and second.status == "draft" and first.doc_number != second.doc_number


def test_approved_report_download_ends_with_an_approval_page(db, people):
    setup = full_setup(db, people)
    approve_all(db, people, setup)
    execute_all(db, people, setup)
    document = approve_report(db, people, setup.version)
    db.refresh(document)
    assert document.status == "approved"
    download = report_docs.download_pdf(db, document)
    text = pdf_text(download)
    assert "Approval record" in text and people.qa.full_name in text and document.sha256 in text


def test_the_report_cannot_be_approved_by_its_author(db, people):
    setup = full_setup(db, people)
    approve_all(db, people, setup)
    execute_all(db, people, setup)
    document = report_docs.generate_report(db, people.ve, setup.version)
    db.commit()
    document.generated_by = people.qa.id
    db.commit()
    from app.core.errors import Conflict

    with pytest.raises(Conflict):
        report_docs.approve_report(db, people.qa, PASSWORD, document)


# ---------------------------------------------------------------- SQL reports

def test_catalog_lists_eight_reports():
    assert len(reports.catalog()) == 8


@pytest.mark.parametrize("key", list(reports.REPORTS))
def test_every_report_runs_and_shows_its_sql(db, people, key):
    validate(db, people, full_setup(db, people))
    report = reports.run_report(db, key)
    assert report["columns"] and report["sql"].startswith("CREATE VIEW")
    assert report["view"] in report["sql"]


def test_validation_status_report_has_the_numbers(db, people):
    setup = full_setup(db, people, name="Numbers App")
    approve_all(db, people, setup)
    execute_all(db, people, setup)
    report = reports.run_report(db, "validation-status")
    columns = report["columns"]
    row = dict(zip(columns, report["rows"][0], strict=True))
    assert row["application_name"] == "Numbers App"
    assert row["requirements_total"] == 3 and row["requirements_covered"] == 3
    assert float(row["coverage_pct"]) == 100.0
    assert row["tests_passed"] == 3 and row["tests_failed"] == 0 and row["tests_not_run"] == 0


def test_traceability_view_shows_a_requirement_without_a_test(db, people):
    from helpers import add_requirements, make_application

    application, _ = make_application(db, people, name="Gap App")
    add_requirements(db, people, application)
    rows = reports.run_report(db, "traceability")["rows"]
    columns = reports.run_report(db, "traceability")["columns"]
    index = columns.index("test_code")
    assert len(rows) == 3 and all(row[index] is None for row in rows)


def test_csv_export(api, db, people):
    validate(db, people, full_setup(db, people))
    response = api("auditor").get("/api/reports/validation-status/csv")
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/csv")
    assert response.text.splitlines()[0].startswith("application_id")


def test_unknown_report_is_not_found(api):
    assert api("auditor").get("/api/reports/does-not-exist").status_code == 404
    assert api("auditor").get("/api/reports/validation-status; DROP TABLE users").status_code == 404
