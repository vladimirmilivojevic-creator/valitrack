"""Electronic signatures (21 CFR Part 11, subpart C, in simplified form).

A signature needs the signer to type the password again (two components: user name from
the session, password typed now). It records who, in which role, what it means, which
record and the hash of the record content at that moment. The row is append-only.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import Conflict, Forbidden
from app.models import ESignature, User
from app.services import audit
from app.services.auth import check_password

# Which roles may sign with which meaning.
MEANING_ROLES: dict[str, set[str]] = {
    "Authored": {"validation_engineer", "admin"},
    "Executed": {"validation_engineer", "tester", "admin"},
    "Reviewed": {"qa_manager"},
    "Approved": {"qa_manager"},
    "Owner approved": {"system_owner"},
    "Released": {"qa_manager"},
    "Closed": {"qa_manager"},
    "Training verified": {"validation_engineer", "admin", "qa_manager"},
}


def sign(
    db: Session,
    user: User,
    password: str,
    *,
    meaning: str,
    entity_type: str,
    entity_id: int,
    entity_label: str,
    record_hash: str,
    comment: str | None = None,
) -> ESignature:
    if user.role not in MEANING_ROLES[meaning]:
        raise Forbidden(f'Your role may not sign with the meaning "{meaning}".')
    check_password(db, user, password, action=f"signature: {meaning}")
    signature = ESignature(
        user_id=user.id,
        signer_name=user.full_name,
        signer_role=user.role,
        meaning=meaning,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_label=entity_label,
        record_hash=record_hash,
        comment=comment,
    )
    db.add(signature)
    db.flush()
    audit.record(
        db,
        user,
        "sign",
        entity_type,
        entity_id,
        entity_label,
        new={"meaning": meaning, "record_hash": record_hash, "signature_hash": signature.signature_hash},
        reason=comment,
    )
    return signature


def forbid_same_person(user: User, other_user_id: int | None, rule: str) -> None:
    """Segregation of duties: the same person may not do both steps."""
    if other_user_id is not None and other_user_id == user.id:
        raise Conflict(rule)


def signatures_for(db: Session, entity_type: str, entity_id: int) -> list[ESignature]:
    return list(
        db.scalars(
            select(ESignature)
            .where(ESignature.entity_type == entity_type, ESignature.entity_id == entity_id)
            .order_by(ESignature.id)
        )
    )
