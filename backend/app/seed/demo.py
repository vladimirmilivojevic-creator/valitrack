"""Loads the demo data through the same services that the application uses.

Because nothing is inserted with raw SQL, the sample data has real signatures, a valid
audit trail hash chain and goes through the same business rules as live data.

    python -m app.seed.demo          # fills an empty database (used when the demo starts)
"""

from datetime import date, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models import (
    Application,
    AppVersion,
    ChangeRequest,
    ConfigItem,
    Deviation,
    TestCase,
    User,
)
from app.seed import demo_data as data
from app.services import (
    applications,
    audit,
    changes,
    configuration,
    deviations,
    report_docs,
    requirements,
    runs,
    support,
    testcases,
    training,
)

DEMO_PASSWORD = "Demo-Valitrack-2026"
DEMO_LOGINS = data.DEMO_LOGINS

ALL_TABLES = (
    "audit_log, e_signatures, report_documents, ticket_comments, support_tickets, training_records, "
    "training_attendees, training_sessions, config_items, deviations, evidence, test_run_steps, test_runs, "
    "change_test_links, change_impacts, change_requests, requirement_test_links, test_steps, test_cases, "
    "requirements, app_versions, application_users, applications, users"
)


class Seeder:
    def __init__(self, db: Session):
        self.db = db
        self.today = date.today()
        self.users: dict[str, User] = {}

    # ------------------------------------------------------------ people

    def create_people(self) -> None:
        password_hash = hash_password(DEMO_PASSWORD)
        for username, full_name, role, department in data.PEOPLE:
            user = User(username=username, full_name=full_name, email=f"{username}@example.com", role=role,
                        department=department, password_hash=password_hash)
            self.db.add(user)
            self.db.flush()
            audit.record(self.db, None, "create", "user", user.id, username,
                         new={"username": username, "role": role, "department": department})
            self.users[username] = user
        self.db.commit()

    def u(self, username: str) -> User:
        return self.users[username]

    # ------------------------------------------------------------ building blocks

    def create_application(self, spec: dict) -> tuple[Application, AppVersion, list, list[TestCase]]:
        sophie = self.u("sophie.val")
        patient, quality, integrity = spec["flags"]
        application = applications.create_application(self.db, sophie, {
            "name": spec["name"], "description": spec["description"], "vendor": spec["vendor"],
            "department": spec["department"], "owner_id": self.u(spec["owner"]).id,
            "gamp_category": spec["gamp"], "intended_use": spec["intended_use"],
            "patient_safety_impact": patient, "product_quality_impact": quality,
            "data_integrity_impact": integrity,
        }, spec["version"])
        version = self.db.scalar(select(AppVersion).where(AppVersion.application_id == application.id))
        reqs = []
        for title, description, rating in spec["requirements"]:
            severity, probability, detectability = rating or (None, None, None)
            reqs.append(requirements.create_requirement(self.db, sophie, application, {
                "kind": "URS", "title": title, "description": description, "severity": severity,
                "probability": probability, "detectability": detectability}))
        for title, description, parent_number in spec.get("functional", []):
            requirements.create_requirement(self.db, sophie, application, {
                "kind": "FS", "parent_id": reqs[parent_number - 1].id, "title": title,
                "description": description, "severity": 2, "probability": 2, "detectability": 2})
        tests = []
        for test in spec["tests"]:
            tests.append(testcases.create_test_case(self.db, sophie, application, {
                "test_type": test["type"], "title": test["title"], "objective": test["objective"],
                "style": test.get("style", "scripted"),
                "steps": [{"action": a, "expected_result": e} for a, e in test["steps"]],
                "requirement_ids": [reqs[n - 1].id for n in test["covers"]]}))
        for name, value, description in spec.get("config", []):
            configuration.create_item(self.db, self.u("tim.admin"), application,
                                      {"name": name, "value": value, "description": description})
        self.db.commit()
        return application, version, reqs, tests

    def approve_baseline_and_tests(self, version: AppVersion, tests: list[TestCase]) -> None:
        eva = self.u("eva.qa")
        applications.approve_urs(self.db, eva, DEMO_PASSWORD, version)
        for test in tests:
            testcases.approve_test_case(self.db, eva, DEMO_PASSWORD, test)
        self.db.commit()

    def execute(self, version: AppVersion, test: TestCase, *, fail_step: int | None = None,
                review: bool = True, change_id: int | None = None):
        lukas, eva = self.u("lukas.test"), self.u("eva.qa")
        run = runs.start_run(self.db, lukas, test, version, change_id)
        for step in run.steps:
            if fail_step == step.step_no:
                runs.record_step(self.db, lukas, run, step.step_no, "failed",
                                 "The result differs from the expectation (see evidence).", None)
            else:
                runs.record_step(self.db, lukas, run, step.step_no, "passed", "Result matches the expectation.", None)
        last = run.steps[-1].step_no
        log = (f"Execution log of {test.code} on {version.version}\n"
               f"Executed by {lukas.full_name}\nResult of step {last}: "
               f"{'FAILED' if fail_step else 'as expected'}\n").encode()
        runs.add_evidence(self.db, lukas, run, last, f"{test.code}-log.txt", "text/plain", log)
        runs.complete_run(self.db, lukas, DEMO_PASSWORD, run)
        if review and run.result != "failed":
            runs.review_run(self.db, eva, DEMO_PASSWORD, run, "Reviewed against the protocol.")
        self.db.commit()
        return run

    def validate(self, version: AppVersion) -> None:
        document = report_docs.generate_report(self.db, self.u("sophie.val"), version)
        report_docs.approve_report(self.db, self.u("eva.qa"), DEMO_PASSWORD, document)
        applications.release_version(self.db, self.u("eva.qa"), DEMO_PASSWORD, version)
        self.db.commit()

    def validated_application(self, spec: dict):
        application, version, reqs, tests = self.create_application(spec)
        self.approve_baseline_and_tests(version, tests)
        for test in tests:
            self.execute(version, test)
        self.validate(version)
        return application, version, reqs, tests

    def assign_users(self, application: Application, usernames: list[str]) -> None:
        roles = {usernames[0]: "key_user"}
        applications.set_application_users(
            self.db, self.u("sophie.val"), application,
            [{"user_id": self.u(n).id, "app_role": roles.get(n, "user")} for n in usernames])
        self.db.commit()

    def train(self, application: Application, version: AppVersion, title: str, attendees: list[str],
              present: list[str], days_ago: int, kind: str = "classroom"):
        sophie = self.u("sophie.val")
        session = training.create_session(self.db, sophie, application, {
            "app_version_id": version.id, "title": title, "session_type": kind, "trainer_id": sophie.id,
            "session_date": self.today - timedelta(days=days_ago), "duration_minutes": 90,
            "materials": f"{application.name} user guide and slides",
            "attendee_ids": [self.u(n).id for n in attendees]})
        training.complete_session(self.db, sophie, DEMO_PASSWORD, session, [self.u(n).id for n in present])
        self.db.commit()

    def change(self, application: Application, requester: str, spec: dict, departments: list[str],
               assessments: list[tuple[str, str, str, bool, str]]) -> ChangeRequest:
        """Create a change and move it through submit, start of assessment and the given assessments."""
        change = changes.create_change(self.db, self.u(requester), application, spec)
        changes.submit(self.db, self.u(requester), change)
        changes.start_assessment(self.db, self.u("sophie.val"), change, departments)
        for who, department, level, affects, comment in assessments:
            changes.assess(self.db, self.u(who), change, department, level, affects, comment)
        self.db.commit()
        return change


# ---------------------------------------------------------------- the story

def seed(db: Session) -> None:
    s = Seeder(db)
    s.create_people()
    sophie, eva, tim = s.u("sophie.val"), s.u("eva.qa"), s.u("tim.admin")
    staff = ["sophie.val", "lukas.test", "anna.berger", "marco.ruf", "julia.egger", "felix.gstrein",
             "hannah.walch", "stefan.pichler", "mara.kofler", "jonas.thaler"]

    # 1. DocuControl: validated v3.2 and a change to v3.3 that is in testing (the main demo story)
    docu, docu_v32, _, docu_tests = s.validated_application(data.DOCUCONTROL)
    s.assign_users(docu, staff)
    s.train(docu, docu_v32, "DocuControl 3.2 for all document users", staff[:9],
            [n for n in staff[:9] if n != "marco.ruf"], 60)

    cr1 = s.change(
        docu, "anna.berger",
        {"title": "Upgrade DocuControl to 3.3", "change_type": "upgrade", "target_version": "3.3",
         "business_need": "The vendor ends support for 3.2 and 3.3 adds a faster review reminder engine.",
         "description": "Upgrade the production system from 3.2 to 3.3 and adapt the email templates.",
         "priority": "high", "planned_release_date": s.today + timedelta(days=21)},
        ["IT", "Regulatory Affairs", "Production"],
        [("tim.admin", "IT", "medium", False, "Upgrade is done on the test server first. Rollback plan exists."),
         ("eva.qa", "Quality Assurance", "low", False, "Requirements stay the same. A full regression set is needed."),
         ("nina.owner", "Regulatory Affairs", "medium", True, "Signature and approval functions are touched, so they must be retested."),
         ("sophie.val", "Production", "low", False, "Recorded for Production after talking to the line lead.")])
    changes.approve(db, eva, DEMO_PASSWORD, cr1, "Approved with a full regression set.")
    db.commit()
    configuration.update_item(db, tim, db.scalar(select(ConfigItem).where(
        ConfigItem.application_id == docu.id, ConfigItem.name.like("Review reminder%"))),
        {"value": "45", "change_request_id": cr1.id}, "Longer reminder time agreed in the change.")
    changes.start_testing(db, sophie, cr1)
    db.commit()
    v33 = db.get(AppVersion, cr1.target_version_id)
    for test in (docu_tests[0], docu_tests[1], docu_tests[2], docu_tests[4]):
        s.execute(v33, test, change_id=cr1.id)
    s.execute(v33, docu_tests[3], fail_step=3, change_id=cr1.id, review=False)
    training.create_session(db, sophie, docu, {
        "app_version_id": v33.id, "title": "DocuControl 3.3: what is new", "session_type": "hands_on",
        "trainer_id": sophie.id, "session_date": s.today + timedelta(days=14), "duration_minutes": 60,
        "materials": "Release notes and a short exercise", "attendee_ids": [s.u(n).id for n in staff[:9]]})
    db.commit()

    # 2. CalTrack: validated, with two changes in the early steps
    cal, cal_v, _, _ = s.validated_application(data.CALTRACK)
    cal_users = ["stefan.pichler", "lukas.test", "anna.berger", "marco.ruf", "felix.gstrein", "jonas.thaler"]
    s.assign_users(cal, cal_users)
    s.train(cal, cal_v, "CalTrack 1.8 introduction", cal_users, cal_users[:4], 45, "hands_on")
    s.change(
        cal, "stefan.pichler",
        {"title": "Longer warning period for due calibrations", "change_type": "configuration",
         "target_version": "1.8.1", "business_need": "Technicians need 45 days of notice to plan the work.",
         "description": "Change the warning period from 30 to 45 days.", "priority": "normal"},
        ["IT", "Production"],
        [("tim.admin", "IT", "low", False, "Simple setting. No technical risk.")])
    cr3 = s.change(
        cal, "marco.ruf",
        {"title": "Barcode scanner support", "change_type": "enhancement", "target_version": "1.9",
         "business_need": "Scanning device tags is faster and avoids typing errors.",
         "description": "Add support for handheld barcode scanners on the register and the calibration form.",
         "priority": "normal", "planned_release_date": s.today + timedelta(days=60), "affects_requirements": True},
        ["IT", "Production", "R&D"],
        [("tim.admin", "IT", "medium", False, "New driver on the shop-floor PCs."),
         ("eva.qa", "Quality Assurance", "low", True, "New requirement for scanning. The baseline must be approved again."),
         ("sophie.val", "Production", "medium", True, "Recorded for Production. The scan step changes the daily routine."),
         ("sophie.val", "R&D", "low", False, "Recorded for R&D. No interface to the lab systems.")])
    assert cr3.status == "pending_approval"

    # 3. SupplierHub: first validation in progress, one failed test with an overdue deviation
    sup, sup_v, _, sup_tests = s.create_application(data.SUPPLIERHUB)
    s.approve_baseline_and_tests(sup_v, sup_tests)
    for test in sup_tests[:3]:
        s.execute(sup_v, test)
    s.execute(sup_v, sup_tests[3], fail_step=2)
    deviation = db.scalar(select(Deviation).where(Deviation.application_id == sup.id))
    deviations.update_deviation(db, sophie, deviation, {
        "owner_id": sophie.id, "due_date": s.today - timedelta(days=4), "severity": "major",
        "root_cause": "The status change dialog stores the signature only after the page is saved.",
        "impact": "A status could be changed without a stored signature."},
        "Initial analysis with the vendor.")
    db.commit()

    # 4. TrainMate: validated 4.0, then a security patch released as 4.1 through change control
    tm, tm_v, _, tm_tests = s.validated_application(data.TRAINMATE)
    tm_users = ["hannah.walch", "julia.egger", "mara.kofler", "jonas.thaler", "anna.berger", "felix.gstrein"]
    s.assign_users(tm, tm_users)
    s.train(tm, tm_v, "TrainMate 4.0 for employees", tm_users, tm_users, 120, "online")
    cr4 = s.change(
        tm, "felix.gstrein",
        {"title": "Security patch 4.0.1", "change_type": "patch", "target_version": "4.0.1",
         "business_need": "The vendor fixed a vulnerability in the login page.",
         "description": "Install the vendor patch on the production server.", "priority": "high"},
        ["IT", "Customer Service"],
        [("tim.admin", "IT", "low", False, "Patch tested on the staging server."),
         ("eva.qa", "Quality Assurance", "low", False, "Functions are unchanged. Run the regression tests."),
         ("sophie.val", "Customer Service", "none", False, "Recorded for Customer Service. No change for users.")])
    changes.approve(db, eva, DEMO_PASSWORD, cr4, "Approved.")
    changes.start_testing(db, sophie, cr4)
    db.commit()
    tm_v2 = db.get(AppVersion, cr4.target_version_id)
    for test in tm_tests:
        s.execute(tm_v2, test, change_id=cr4.id)
    changes.complete_testing(db, sophie, cr4)
    document = report_docs.generate_report(db, sophie, tm_v2)
    report_docs.approve_report(db, eva, DEMO_PASSWORD, document)
    changes.release(db, eva, DEMO_PASSWORD, cr4, "Released after the regression tests.")
    db.commit()
    s.train(tm, tm_v2, "TrainMate 4.0.1 what changed", tm_users, tm_users[:3], 3, "online")

    # 5. YieldCalc: custom spreadsheet, requirements incomplete (the gate shows what is missing)
    s.create_application(data.YIELDCALC)

    # 6. PatchGuard: infrastructure tool, IQ only, one change submitted
    pg, _, _, _ = s.validated_application(data.PATCHGUARD)
    s.assign_users(pg, ["tim.admin", "felix.gstrein"])
    pg_change = changes.create_change(db, s.u("felix.gstrein"), pg, {
        "title": "Upgrade patch agent to 2.4", "change_type": "upgrade", "target_version": "2.4",
        "business_need": "Version 2.3 does not support the new Windows build.",
        "description": "Roll out agent 2.4 to all managed PCs in two waves.", "priority": "normal"})
    changes.submit(db, s.u("felix.gstrein"), pg_change)
    db.commit()

    # support tickets
    for application_name, reporter, category, priority, summary, description, status, resolution in data.TICKETS:
        application = db.scalar(select(Application).where(Application.name == application_name))
        ticket = support.create_ticket(db, s.u(reporter), {
            "application_id": application.id, "summary": summary, "description": description,
            "category": category, "priority": priority})
        update = {}
        if status != "open":
            update.update(assignee_id=sophie.id if category != "access" else tim.id, status=status)
            if resolution:
                update["resolution"] = resolution
            support.add_comment(db, sophie, ticket, resolution or "Looking into it.")
            support.update_ticket(db, sophie, ticket, update)
        db.commit()


def reset_and_seed(db: Session) -> None:
    """Demo only: empty every table (the only time the append-only tables may be emptied) and reload."""
    db.execute(text("SET LOCAL valitrack.allow_reset = 'on'"))
    db.execute(text(f"TRUNCATE {ALL_TABLES} RESTART IDENTITY CASCADE"))
    db.commit()
    seed(db)


def seed_if_empty() -> bool:
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(User)) == 0:
            seed(db)
            return True
    return False


if __name__ == "__main__":
    print("Demo data loaded." if seed_if_empty() else "The database already has data. Nothing to do.")
