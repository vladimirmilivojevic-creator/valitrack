"""Test cases (IQ, OQ, PQ), their steps, links to requirements and QA approval."""

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.errors import Conflict, Invalid
from app.models import Application, Requirement, RequirementTestLink, TestCase, TestStep, User
from app.services import audit, signatures
from app.services.common import canonical_hash, require_permission, require_text, row_dict, utcnow


def _step_data(steps: list[dict] | None) -> list[dict]:
    cleaned = []
    for number, step in enumerate(steps or [], start=1):
        cleaned.append({
            "step_no": number,
            "action": require_text(step.get("action"), f"The action of step {number}"),
            "expected_result": require_text(step.get("expected_result"), f"The expected result of step {number}"),
        })
    return cleaned


def snapshot(test_case: TestCase) -> dict:
    """The content that an approval signature covers."""
    return {
        "code": test_case.code, "type": test_case.test_type, "title": test_case.title,
        "objective": test_case.objective, "preconditions": test_case.preconditions,
        "style": test_case.style, "revision": test_case.revision,
        "steps": [[s.step_no, s.action, s.expected_result] for s in test_case.steps],
    }


def linked_requirement_ids(db: Session, test_case_id: int) -> list[int]:
    return list(db.scalars(
        select(RequirementTestLink.requirement_id)
        .where(RequirementTestLink.test_case_id == test_case_id)
        .order_by(RequirementTestLink.requirement_id)
    ))


def create_test_case(db: Session, user: User, application: Application, data: dict) -> TestCase:
    require_permission(user, "test.write")
    test_type = data.get("test_type")
    if test_type not in ("IQ", "OQ", "PQ"):
        raise Invalid("The test type must be IQ, OQ or PQ.")
    style = data.get("style", "scripted")
    if style not in ("scripted", "unscripted"):
        raise Invalid("The style must be scripted or unscripted.")
    count = db.scalar(select(func.count()).select_from(TestCase).where(TestCase.application_id == application.id))
    test_case = TestCase(
        application_id=application.id,
        code=f"TC-{count + 1:03d}",
        test_type=test_type,
        title=require_text(data.get("title"), "The title"),
        objective=require_text(data.get("objective"), "The objective"),
        preconditions=data.get("preconditions"),
        style=style,
        created_by=user.id,
    )
    for step in _step_data(data.get("steps")):
        test_case.steps.append(TestStep(**step))
    db.add(test_case)
    db.flush()
    audit.record(db, user, "create", "test_case", test_case.id, f"{application.name} {test_case.code}",
                 new={**row_dict(test_case), "steps": len(test_case.steps)})
    if data.get("requirement_ids"):
        set_requirement_links(db, user, test_case, data["requirement_ids"])
    return test_case


def update_test_case(db: Session, user: User, test_case: TestCase, data: dict, reason: str) -> TestCase:
    """Editing an approved test case sends it back to draft: it needs a new approval."""
    require_permission(user, "test.write")
    reason = require_text(reason, "A reason for the change")
    if test_case.status == "retired":
        raise Conflict("A retired test case cannot be changed.")
    before = snapshot(test_case)
    was_approved = test_case.status == "approved"
    for key in ("title", "objective", "preconditions"):
        if key in data:
            setattr(test_case, key, data[key])
    if "style" in data:
        if data["style"] not in ("scripted", "unscripted"):
            raise Invalid("The style must be scripted or unscripted.")
        test_case.style = data["style"]
    if "steps" in data:
        new_steps = _step_data(data["steps"])
        test_case.steps.clear()
        db.flush()
        for step in new_steps:
            test_case.steps.append(TestStep(**step))
    db.flush()
    after = snapshot(test_case)
    if before == after:
        return test_case
    test_case.revision += 1
    if was_approved:
        test_case.status = "draft"
        test_case.approved_by = None
        test_case.approved_at = None
    db.flush()
    audit.record(db, user, "update", "test_case", test_case.id, test_case.code,
                 old=before, new=snapshot(test_case), reason=reason)
    return test_case


def set_requirement_links(db: Session, user: User, test_case: TestCase, requirement_ids: list[int]) -> None:
    require_permission(user, "test.write")
    requirements = list(db.scalars(select(Requirement).where(Requirement.id.in_(requirement_ids))))
    if len(requirements) != len(set(requirement_ids)):
        raise Invalid("One of the requirements does not exist.")
    for requirement in requirements:
        if requirement.application_id != test_case.application_id or requirement.status != "active":
            raise Invalid("A test case can only cover active requirements of its own application.")
        if test_case.style == "unscripted" and requirement.risk_level != "low":
            raise Invalid("Unscripted testing is only allowed for low-risk requirements.")
    before = linked_requirement_ids(db, test_case.id)
    after = sorted(set(requirement_ids))
    if before == after:
        return
    db.execute(delete(RequirementTestLink).where(RequirementTestLink.test_case_id == test_case.id))
    for requirement_id in after:
        db.add(RequirementTestLink(requirement_id=requirement_id, test_case_id=test_case.id))
    db.flush()
    audit.record(db, user, "link_requirements", "test_case", test_case.id, test_case.code,
                 old={"requirement_ids": before}, new={"requirement_ids": after})


def approve_test_case(db: Session, user: User, password: str, test_case: TestCase, comment: str | None = None):
    require_permission(user, "test.approve")
    if test_case.status != "draft":
        raise Conflict("Only a draft test case can be approved.")
    if test_case.style == "scripted" and not test_case.steps:
        raise Conflict("A scripted test case needs at least one step.")
    if not linked_requirement_ids(db, test_case.id):
        raise Conflict("Link the test case to at least one requirement before approving it.")
    signatures.forbid_same_person(user, test_case.created_by, "The author of a test case cannot approve it.")
    signature = signatures.sign(
        db, user, password, meaning="Approved", entity_type="test_case", entity_id=test_case.id,
        entity_label=f"{test_case.code} revision {test_case.revision}",
        record_hash=canonical_hash(snapshot(test_case)), comment=comment,
    )
    test_case.status = "approved"
    test_case.approved_by = user.id
    test_case.approved_at = utcnow()
    db.flush()
    audit.record(db, user, "approve", "test_case", test_case.id, test_case.code,
                 old={"status": "draft"}, new={"status": "approved", "revision": test_case.revision})
    return signature


def retire_test_case(db: Session, user: User, test_case: TestCase, reason: str) -> TestCase:
    require_permission(user, "test.write")
    reason = require_text(reason, "A reason for retiring the test case")
    if test_case.status == "retired":
        raise Conflict("The test case is already retired.")
    old_status = test_case.status
    test_case.status = "retired"
    db.flush()
    audit.record(db, user, "retire", "test_case", test_case.id, test_case.code,
                 old={"status": old_status}, new={"status": "retired"}, reason=reason)
    return test_case
