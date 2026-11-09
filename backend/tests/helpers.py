"""Building blocks for the tests: a small validated application, built through the services."""

from types import SimpleNamespace

from app.services import applications, report_docs, requirements, runs, testcases
from conftest import PASSWORD

RATINGS = [(3, 2, 3), (2, 2, 2), (1, 1, 1)]  # high, medium, low


def make_application(db, people, *, name="Alpha", gamp=4, flags=(False, True, True), version="1.0"):
    application = applications.create_application(db, people.ve, {
        "name": name, "description": "Test application", "vendor": "Test vendor", "department": "Quality Assurance",
        "owner_id": people.owner.id, "gamp_category": gamp, "intended_use": "Testing the tracker",
        "patient_safety_impact": flags[0], "product_quality_impact": flags[1], "data_integrity_impact": flags[2],
    }, version)
    db.commit()
    from sqlalchemy import select

    from app.models import AppVersion

    version_row = db.scalar(select(AppVersion).where(AppVersion.application_id == application.id))
    return application, version_row


def add_requirements(db, people, application, ratings=RATINGS):
    created = []
    for number, (s, p, d) in enumerate(ratings, start=1):
        created.append(requirements.create_requirement(db, people.ve, application, {
            "title": f"Requirement {number}", "description": f"The system does thing {number}.",
            "severity": s, "probability": p, "detectability": d}))
    db.commit()
    return created


def add_test(db, people, application, test_type, covers, *, style="scripted", title=None):
    test = testcases.create_test_case(db, people.ve, application, {
        "test_type": test_type, "title": title or f"{test_type} test", "objective": f"Check {test_type}",
        "style": style,
        "steps": [] if style == "unscripted" else [
            {"action": "Do the first thing", "expected_result": "It works"},
            {"action": "Do the second thing", "expected_result": "It also works"}],
        "requirement_ids": [r.id for r in covers]})
    db.commit()
    return test


def full_setup(db, people, *, name="Alpha", gamp=4, flags=(False, True, True)):
    """Application with three requirements (high, medium, low) and an approved IQ, OQ and PQ test."""
    application, version = make_application(db, people, name=name, gamp=gamp, flags=flags)
    reqs = add_requirements(db, people, application)
    tests = [
        add_test(db, people, application, "IQ", [reqs[2]]),
        add_test(db, people, application, "OQ", [reqs[0], reqs[1]]),
        add_test(db, people, application, "PQ", [reqs[0]]),
    ]
    return SimpleNamespace(application=application, version=version, reqs=reqs, tests=tests)


def approve_all(db, people, setup):
    applications.approve_urs(db, people.qa, PASSWORD, setup.version)
    for test in setup.tests:
        testcases.approve_test_case(db, people.qa, PASSWORD, test)
    db.commit()


def execute(db, people, version, test, *, fail_step=None, review=True, change_id=None):
    run = runs.start_run(db, people.tester, test, version, change_id)
    for step in run.steps:
        if step.step_no == fail_step:
            runs.record_step(db, people.tester, run, step.step_no, "failed", "It did not work", None)
        else:
            runs.record_step(db, people.tester, run, step.step_no, "passed", "As expected", None)
    runs.complete_run(db, people.tester, PASSWORD, run)
    if review and run.result == "passed":
        runs.review_run(db, people.qa, PASSWORD, run, "Reviewed")
    db.commit()
    return run


def execute_all(db, people, setup):
    for test in setup.tests:
        execute(db, people, setup.version, test)


def approve_report(db, people, version):
    document = report_docs.generate_report(db, people.ve, version)
    report_docs.approve_report(db, people.qa, PASSWORD, document)
    db.commit()
    return document


def validate(db, people, setup):
    """Run the whole lifecycle until the version is validated."""
    approve_all(db, people, setup)
    execute_all(db, people, setup)
    approve_report(db, people, setup.version)
    applications.release_version(db, people.qa, PASSWORD, setup.version)
    db.commit()
    return setup
