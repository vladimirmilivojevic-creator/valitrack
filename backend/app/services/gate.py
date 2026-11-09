"""The release gate: can this version be released as validated?

evaluate_release_gate() looks at the facts in the database and answers with a list of
checks. Every check has a plain sentence, so the screen can explain *why* a release is
blocked instead of just saying "no". The same facts feed the PDF report and the state hash
that ties an approved report to the exact state it describes.
"""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFound
from app.models import (
    Application,
    AppVersion,
    Deviation,
    ReportDocument,
    Requirement,
    RequirementTestLink,
    TestCase,
    TestRun,
)
from app.services.common import canonical_hash
from app.services.gamp import required_test_types

OPEN_DEVIATION_STATUSES = ("open", "in_progress", "resolved")


@dataclass
class GateCheck:
    key: str
    label: str
    passed: bool
    detail: str


@dataclass
class GateResult:
    version_id: int
    checks: list[GateCheck]
    state_hash: str
    facts: dict = field(default_factory=dict, repr=False)

    @property
    def ready_for_report(self) -> bool:
        """Everything except the report approval itself is in order."""
        return all(c.passed for c in self.checks if c.key != "report_approved")

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    def failing(self) -> list[GateCheck]:
        return [c for c in self.checks if not c.passed]


def requirements_baseline(db: Session, application_id: int) -> list[dict]:
    rows = db.scalars(
        select(Requirement)
        .where(Requirement.application_id == application_id, Requirement.status == "active")
        .order_by(Requirement.code)
    ).all()
    codes = {r.id: r.code for r in rows}
    return [
        {
            "code": r.code,
            "kind": r.kind,
            "parent": codes.get(r.parent_id),
            "title": r.title,
            "description": r.description,
            "severity": r.severity,
            "probability": r.probability,
            "detectability": r.detectability,
        }
        for r in rows
    ]


def baseline_hash(db: Session, application_id: int) -> str:
    return canonical_hash(requirements_baseline(db, application_id))


def _codes(items: list[str], limit: int = 6) -> str:
    shown = ", ".join(items[:limit])
    return shown + (f" and {len(items) - limit} more" if len(items) > limit else "")


def collect_facts(db: Session, version: AppVersion) -> dict:
    application = db.get(Application, version.application_id)
    requirements = list(
        db.scalars(
            select(Requirement)
            .where(Requirement.application_id == application.id, Requirement.status == "active")
            .order_by(Requirement.code)
        )
    )
    approved_tests = {
        t.id: t
        for t in db.scalars(
            select(TestCase).where(TestCase.application_id == application.id, TestCase.status == "approved")
        )
    }
    tests_of_requirement: dict[int, list[TestCase]] = {r.id: [] for r in requirements}
    for link in db.scalars(
        select(RequirementTestLink).where(RequirementTestLink.requirement_id.in_(list(tests_of_requirement)))
    ):
        test = approved_tests.get(link.test_case_id)
        if test is not None:
            tests_of_requirement[link.requirement_id].append(test)

    latest_run: dict[int, TestRun] = {}
    runs = db.scalars(
        select(TestRun)
        .where(TestRun.app_version_id == version.id, TestRun.status == "completed")
        .order_by(TestRun.completed_at.desc(), TestRun.id.desc())
    )
    for run in runs:
        latest_run.setdefault(run.test_case_id, run)

    deviations = list(db.scalars(select(Deviation).where(Deviation.app_version_id == version.id)))
    report = db.scalars(
        select(ReportDocument)
        .where(ReportDocument.app_version_id == version.id, ReportDocument.status == "approved")
        .order_by(ReportDocument.id.desc())
    ).first()
    return {
        "application": application,
        "requirements": requirements,
        "approved_tests": approved_tests,
        "tests_of_requirement": tests_of_requirement,
        "latest_run": latest_run,
        "deviations": deviations,
        "approved_report": report,
    }


def _state_hash(baseline: str, facts: dict) -> str:
    tested_ids = {t.id for tests in facts["tests_of_requirement"].values() for t in tests}
    tests = []
    for test_id in sorted(tested_ids):
        run = facts["latest_run"].get(test_id)
        tests.append(
            [test_id, facts["approved_tests"][test_id].revision,
             run.id if run else None, run.result if run else None, bool(run and run.reviewed_at)]
        )
    deviations = sorted([d.id, d.status] for d in facts["deviations"])
    return canonical_hash({"baseline": baseline, "tests": tests, "deviations": deviations})


def evaluate_release_gate(db: Session, version_id: int) -> GateResult:
    version = db.get(AppVersion, version_id)
    if version is None:
        raise NotFound(f"Version {version_id} was not found.")
    facts = collect_facts(db, version)
    application = facts["application"]
    requirements = facts["requirements"]
    tests_of = facts["tests_of_requirement"]
    latest_run = facts["latest_run"]
    checks: list[GateCheck] = []

    # 1. The requirements baseline is approved and has not changed since.
    current_baseline = baseline_hash(db, application.id)
    if not requirements:
        checks.append(GateCheck("urs_approved", "Requirements approved", False, "No requirements are defined yet."))
    elif not version.urs_approved:
        checks.append(GateCheck("urs_approved", "Requirements approved", False,
                                "The requirements (URS) have not been approved by QA yet."))
    elif version.urs_baseline_hash != current_baseline:
        checks.append(GateCheck("urs_approved", "Requirements approved", False,
                                "The requirements were changed after they were approved. They need a new approval."))
    else:
        checks.append(GateCheck("urs_approved", "Requirements approved", True,
                                f"{len(requirements)} requirements approved and unchanged."))

    # 2. Every requirement has a risk rating.
    unrated = [r.code for r in requirements if r.risk_level is None]
    checks.append(GateCheck(
        "risk_rated", "Risk assessment complete", not unrated and bool(requirements),
        "Every requirement has a risk rating." if not unrated and requirements
        else (f"{len(unrated)} requirements have no risk rating: {_codes(unrated)}." if unrated
              else "There is nothing to rate yet."),
    ))

    # 3. Every requirement is covered by an approved test (scripted unless the risk is low).
    uncovered = []
    for r in requirements:
        tests = tests_of[r.id]
        ok = bool(tests) and (r.risk_level == "low" or any(t.style == "scripted" for t in tests))
        if not ok:
            uncovered.append(r.code)
    checks.append(GateCheck(
        "coverage", "Every requirement has a test", not uncovered and bool(requirements),
        f"All {len(requirements)} requirements have an approved test." if not uncovered and requirements
        else (f"{len(uncovered)} of {len(requirements)} requirements have no suitable approved test: "
              f"{_codes(uncovered)}." if uncovered else "There is nothing to cover yet."),
    ))

    # 4. The test types that GAMP asks for exist and passed.
    needed = required_test_types(application.gamp_category)
    missing_types = []
    for test_type in needed:
        passed_of_type = [
            t for t in facts["approved_tests"].values()
            if t.test_type == test_type and (run := latest_run.get(t.id)) and run.result == "passed"
        ]
        if not passed_of_type:
            missing_types.append(test_type)
    checks.append(GateCheck(
        "required_types", f"{' + '.join(needed)} tests passed (GAMP category {application.gamp_category})",
        not missing_types,
        "All required test types have at least one passed test." if not missing_types
        else f"No passed test yet for: {', '.join(missing_types)}.",
    ))

    # 5. Every test linked to a requirement was executed on this version and passed.
    tested = {t.id: t for tests in tests_of.values() for t in tests}
    not_run = sorted(t.code for t in tested.values() if t.id not in latest_run)
    not_passed = sorted(t.code for t in tested.values()
                        if t.id in latest_run and latest_run[t.id].result != "passed")
    problems = []
    if not_run:
        problems.append(f"{len(not_run)} not executed yet: {_codes(not_run)}")
    if not_passed:
        problems.append(f"{len(not_passed)} did not pass: {_codes(not_passed)}")
    checks.append(GateCheck(
        "executed", "All tests executed and passed", not problems and bool(tested),
        f"All {len(tested)} tests passed on version {version.version}." if not problems and tested
        else ("; ".join(problems) + "." if problems else "No tests are linked to requirements yet."),
    ))

    # 6. Tests of high-risk requirements are reviewed by QA.
    high_tests = {t.id for r in requirements if r.risk_level == "high" for t in tests_of[r.id]}
    unreviewed = sorted(
        tested[i].code for i in high_tests if i in latest_run and latest_run[i].reviewed_at is None
    )
    checks.append(GateCheck(
        "reviewed", "High-risk tests reviewed by QA", not unreviewed,
        "Tests of high-risk requirements are reviewed." if not unreviewed
        else f"{len(unreviewed)} tests wait for QA review: {_codes(unreviewed)}.",
    ))

    # 7. No open deviations.
    open_deviations = sorted(d.code for d in facts["deviations"] if d.status in OPEN_DEVIATION_STATUSES)
    checks.append(GateCheck(
        "deviations", "No open deviations", not open_deviations,
        "All deviations are closed or accepted." if not open_deviations
        else f"{len(open_deviations)} deviations are still open: {_codes(open_deviations)}.",
    ))

    state_hash = _state_hash(current_baseline, facts)

    # 8. A validation report was approved for exactly this state.
    report = facts["approved_report"]
    if report is None:
        checks.append(GateCheck("report_approved", "Validation report approved", False,
                                "No validation report has been approved yet."))
    elif report.state_hash != state_hash:
        checks.append(GateCheck("report_approved", "Validation report approved", False,
                                "The approved report is out of date. Something changed after it was approved."))
    else:
        checks.append(GateCheck("report_approved", "Validation report approved", True,
                                f"Report {report.doc_number} is approved and matches the current state."))

    return GateResult(version_id=version.id, checks=checks, state_hash=state_hash, facts=facts)
