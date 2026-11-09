"""Change control: request -> impact assessment -> approval -> testing -> release.

A change to a validated application is never done "just like that". Each step is a
state of the change request, each state has one rule for who may move it forward,
and the important steps are electronically signed.

    draft -> submitted -> impact_assessment -> pending_approval -> approved
          -> testing -> ready_for_release -> released        (rejected / cancelled on the way)
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import Conflict, Forbidden, Invalid
from app.core.permissions import DEPARTMENTS
from app.models import (
    Application,
    AppVersion,
    ChangeImpact,
    ChangeRequest,
    ChangeTestLink,
    Requirement,
    RequirementTestLink,
    TestCase,
    User,
)
from app.services import audit, signatures
from app.services.applications import apply_release
from app.services.common import canonical_hash, require_permission, require_text, row_dict, utcnow
from app.services.gate import baseline_hash, evaluate_release_gate

CHANGE_TYPES = ("bug_fix", "enhancement", "configuration", "upgrade", "patch")
OPEN_STATUSES = ("draft", "submitted", "impact_assessment", "pending_approval", "approved",
                 "testing", "ready_for_release")
IMPACT_LEVELS = ("none", "low", "medium", "high")


def snapshot(db: Session, change: ChangeRequest) -> dict:
    application = db.get(Application, change.application_id)
    return {
        "code": change.code, "application": application.name, "title": change.title,
        "type": change.change_type, "business_need": change.business_need,
        "description": change.description, "target_version": change.target_version,
        "priority": change.priority, "affects_requirements": change.affects_requirements,
        "risk_level": change.risk_level, "requires_revalidation": change.requires_revalidation,
        "impacts": sorted([i.department, i.impact_level, i.affects_validated_state, i.comment]
                          for i in change.impacts),
    }


def _live_version(db: Session, application_id: int) -> AppVersion | None:
    return db.scalar(select(AppVersion).where(AppVersion.application_id == application_id,
                                              AppVersion.status == "validated"))


def _set_status(db: Session, user: User, change: ChangeRequest, new_status: str, reason: str | None = None):
    old_status = change.status
    change.status = new_status
    db.flush()
    audit.record(db, user, "status_change", "change_request", change.id, change.code,
                 old={"status": old_status}, new={"status": new_status}, reason=reason)


def create_change(db: Session, user: User, application: Application, data: dict) -> ChangeRequest:
    require_permission(user, "change.create")
    if data.get("change_type") not in CHANGE_TYPES:
        raise Invalid("Unknown change type.")
    if _live_version(db, application.id) is None:
        raise Conflict("This application has no validated version yet. Finish the first validation before "
                       "using change control.")
    target = require_text(data.get("target_version"), "The target version", 1)
    taken = {v.version for v in db.scalars(select(AppVersion).where(AppVersion.application_id == application.id))}
    taken |= {c.target_version for c in db.scalars(
        select(ChangeRequest).where(ChangeRequest.application_id == application.id,
                                    ChangeRequest.status.in_(OPEN_STATUSES)))}
    if target in taken:
        raise Conflict(f"Version {target} already exists or is planned in another change.")
    change = ChangeRequest(
        application_id=application.id,
        title=require_text(data.get("title"), "The title"),
        change_type=data["change_type"],
        business_need=require_text(data.get("business_need"), "The business need"),
        description=require_text(data.get("description"), "The description"),
        priority=data.get("priority", "normal"),
        requested_by=user.id,
        target_version=target,
        planned_release_date=data.get("planned_release_date"),
        affects_requirements=bool(data.get("affects_requirements", False)),
    )
    db.add(change)
    db.flush()
    audit.record(db, user, "create", "change_request", change.id, change.code, new=row_dict(change))
    return change


def update_change(db: Session, user: User, change: ChangeRequest, data: dict, reason: str) -> ChangeRequest:
    if change.status not in ("draft", "submitted"):
        raise Conflict("A change can only be edited before the impact assessment starts.")
    if change.requested_by != user.id:
        require_permission(user, "change.coordinate")
    reason = require_text(reason, "A reason for the change")
    before = row_dict(change)
    for key in ("title", "business_need", "description", "priority", "planned_release_date",
                "affects_requirements", "target_version", "change_type"):
        if key in data:
            setattr(change, key, data[key])
    if change.change_type not in CHANGE_TYPES:
        raise Invalid("Unknown change type.")
    db.flush()
    old, new = audit.changed_fields(before, row_dict(change))
    if new:
        audit.record(db, user, "update", "change_request", change.id, change.code, old, new, reason)
    return change


def submit(db: Session, user: User, change: ChangeRequest) -> ChangeRequest:
    if change.status != "draft":
        raise Conflict("Only a draft can be submitted.")
    if change.requested_by != user.id:
        require_permission(user, "change.coordinate")
    _set_status(db, user, change, "submitted")
    return change


def start_assessment(db: Session, user: User, change: ChangeRequest, departments: list[str]) -> ChangeRequest:
    """The coordinator decides which departments must give an impact assessment."""
    require_permission(user, "change.coordinate")
    if change.status != "submitted":
        raise Conflict("The impact assessment can only start for a submitted change.")
    chosen = set(departments) | {"Quality Assurance"}
    unknown = chosen - set(DEPARTMENTS)
    if unknown:
        raise Invalid(f"Unknown department: {', '.join(sorted(unknown))}.")
    for department in DEPARTMENTS:
        if department in chosen:
            change.impacts.append(ChangeImpact(department=department))
    db.flush()
    audit.record(db, user, "request_impacts", "change_request", change.id, change.code,
                 new={"departments": sorted(chosen)})
    _set_status(db, user, change, "impact_assessment")
    return change


def assess(db: Session, user: User, change: ChangeRequest, department: str, impact_level: str,
           affects_validated_state: bool, comment: str) -> ChangeImpact:
    require_permission(user, "change.assess")
    if change.status != "impact_assessment":
        raise Conflict("This change is not in the impact assessment step.")
    if impact_level not in IMPACT_LEVELS:
        raise Invalid("The impact level must be none, low, medium or high.")
    impact = next((i for i in change.impacts if i.department == department), None)
    if impact is None:
        raise Invalid(f"{department} was not asked for an assessment.")
    comment = require_text(comment, "A comment")
    old = {"impact_level": impact.impact_level, "affects_validated_state": impact.affects_validated_state,
           "comment": impact.comment}
    impact.assessor_id = user.id
    impact.impact_level = impact_level
    impact.affects_validated_state = affects_validated_state
    impact.comment = comment
    impact.assessed_at = utcnow()
    db.flush()
    audit.record(db, user, "assess", "change_request", change.id, f"{change.code} / {department}", old,
                 {"impact_level": impact_level, "affects_validated_state": affects_validated_state,
                  "comment": comment})
    if all(i.assessed_at is not None for i in change.impacts):
        _complete_assessment(db, user, change)
    return impact


def _complete_assessment(db: Session, user: User, change: ChangeRequest) -> None:
    """All departments answered: work out the risk of the change and ask for approval."""
    order = {"none": 0, "low": 1, "medium": 2, "high": 3}
    worst = max((order[i.impact_level] for i in change.impacts), default=0)
    risk = "high" if worst == 3 else "medium" if worst == 2 else "low"
    if risk == "low" and change.change_type in ("upgrade", "enhancement"):
        risk = "medium"  # new functions always carry at least medium risk
    change.risk_level = risk
    change.requires_revalidation = any(i.affects_validated_state for i in change.impacts)
    db.flush()
    audit.record(db, user, "assess_risk", "change_request", change.id, change.code,
                 new={"risk_level": risk, "requires_revalidation": change.requires_revalidation})
    _set_status(db, user, change, "pending_approval")


def required_meanings(change: ChangeRequest) -> list[str]:
    return ["Approved", "Owner approved"] if change.risk_level == "high" else ["Approved"]


def approve(db: Session, user: User, password: str, change: ChangeRequest, comment: str | None = None):
    require_permission(user, "change.approve")
    if change.status != "pending_approval":
        raise Conflict("This change is not waiting for approval.")
    signatures.forbid_same_person(user, change.requested_by, "The person who requested a change cannot approve it.")
    meaning = "Owner approved" if user.role == "system_owner" else "Approved"
    if meaning not in required_meanings(change):
        raise Conflict("The system owner only signs high-risk changes.")
    already = {s.meaning for s in signatures.signatures_for(db, "change_request", change.id)}
    if meaning in already:
        raise Conflict(f'The change already has a signature with the meaning "{meaning}".')
    signature = signatures.sign(
        db, user, password, meaning=meaning, entity_type="change_request", entity_id=change.id,
        entity_label=change.code, record_hash=canonical_hash(snapshot(db, change)), comment=comment,
    )
    already.add(meaning)
    if set(required_meanings(change)) <= already:
        _create_target_version(db, user, change)
        _set_status(db, user, change, "approved")
    return signature


def reject(db: Session, user: User, password: str, change: ChangeRequest, reason: str):
    require_permission(user, "change.approve")
    if user.role != "qa_manager":
        raise Forbidden("Only the QA manager can reject a change.")
    reason = require_text(reason, "A reason for the rejection")
    if change.status != "pending_approval":
        raise Conflict("This change is not waiting for approval.")
    signature = signatures.sign(
        db, user, password, meaning="Reviewed", entity_type="change_request", entity_id=change.id,
        entity_label=f"{change.code} rejected", record_hash=canonical_hash(snapshot(db, change)), comment=reason,
    )
    change.decision_reason = reason
    _set_status(db, user, change, "rejected", reason)
    return signature


def _create_target_version(db: Session, user: User, change: ChangeRequest) -> AppVersion:
    """Approval creates the version that will be tested and released."""
    application = db.get(Application, change.application_id)
    live = _live_version(db, application.id)
    version = AppVersion(
        application_id=application.id, version=change.target_version, status="in_validation",
        created_by=change.requested_by,
        release_notes=f"{change.code}: {change.title}",
    )
    inherits = live is not None and live.urs_approved and not change.affects_requirements
    if inherits:
        version.urs_approved = True
        version.urs_baseline_hash = baseline_hash(db, application.id)
        version.urs_approved_at = utcnow()
    db.add(version)
    db.flush()
    change.target_version_id = version.id
    db.flush()
    audit.record(db, user, "create", "app_version", version.id, f"{application.name} {version.version}",
                 new={**row_dict(version), "requirements": "inherited" if inherits else "must be approved again"})
    return version


def start_testing(db: Session, user: User, change: ChangeRequest, test_case_ids: list[int] | None = None):
    """Choose the tests that prove the change did not break the validated state (regression set)."""
    require_permission(user, "change.coordinate")
    if change.status != "approved":
        raise Conflict("Testing can only start after the change is approved.")
    covering = select(RequirementTestLink.test_case_id).join(
        Requirement, Requirement.id == RequirementTestLink.requirement_id
    ).where(Requirement.application_id == change.application_id, Requirement.status == "active")
    candidates = {
        t.id: t for t in db.scalars(select(TestCase).where(
            TestCase.application_id == change.application_id, TestCase.status == "approved",
            TestCase.id.in_(covering)))
    }
    chosen = test_case_ids if test_case_ids is not None else list(candidates)
    if not chosen:
        raise Conflict("There are no approved test cases to run. Write and approve tests first.")
    bad = [i for i in chosen if i not in candidates]
    if bad:
        raise Invalid("Only approved test cases that cover a requirement of this application can be chosen.")
    for test_id in chosen:
        db.add(ChangeTestLink(change_id=change.id, test_case_id=test_id))
    db.flush()
    audit.record(db, user, "plan_tests", "change_request", change.id, change.code,
                 new={"test_cases": sorted(candidates[i].code for i in chosen)})
    _set_status(db, user, change, "testing")


def complete_testing(db: Session, user: User, change: ChangeRequest) -> None:
    require_permission(user, "change.coordinate")
    if change.status != "testing":
        raise Conflict("The change is not in testing.")
    gate = evaluate_release_gate(db, change.target_version_id)
    if not gate.ready_for_report:
        open_items = "; ".join(f"{c.label}: {c.detail}" for c in gate.failing() if c.key != "report_approved")
        raise Conflict(f"Testing is not finished. {open_items}")
    _set_status(db, user, change, "ready_for_release")


def release(db: Session, user: User, password: str, change: ChangeRequest, comment: str | None = None):
    require_permission(user, "change.release")
    if change.status != "ready_for_release":
        raise Conflict("The change is not ready for release.")
    signatures.forbid_same_person(user, change.requested_by, "The person who requested a change cannot release it.")
    gate = evaluate_release_gate(db, change.target_version_id)
    if not gate.passed:
        raise Conflict("The release gate is not open: " + "; ".join(c.label for c in gate.failing()) + ".")
    version = db.get(AppVersion, change.target_version_id)
    signature = signatures.sign(
        db, user, password, meaning="Released", entity_type="change_request", entity_id=change.id,
        entity_label=change.code,
        record_hash=canonical_hash({"change": snapshot(db, change), "state": gate.state_hash}), comment=comment,
    )
    apply_release(db, user, version)
    change.released_at = utcnow()
    _set_status(db, user, change, "released")
    return signature


def cancel(db: Session, user: User, change: ChangeRequest, reason: str) -> None:
    if change.requested_by != user.id:
        require_permission(user, "change.coordinate")
    reason = require_text(reason, "A reason for cancelling")
    if change.status not in ("draft", "submitted", "impact_assessment", "pending_approval", "approved"):
        raise Conflict("A change that is already in testing cannot be cancelled. Finish it or reject the release.")
    if change.target_version_id:
        version = db.get(AppVersion, change.target_version_id)
        version.status = "retired"
        audit.record(db, user, "retire", "app_version", version.id, version.version,
                     old={"status": "in_validation"}, new={"status": "retired"}, reason=reason)
    change.decision_reason = reason
    _set_status(db, user, change, "cancelled", reason)
