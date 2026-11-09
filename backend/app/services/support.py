"""User support tickets. Second-level support: the validation engineer works the tickets."""

from sqlalchemy.orm import Session

from app.core.errors import Conflict, Invalid
from app.models import ChangeRequest, SupportTicket, TicketComment, User
from app.services import audit
from app.services.common import require_permission, require_text, row_dict, utcnow

CATEGORIES = ("access", "how_to", "defect", "configuration", "other")
PRIORITIES = ("low", "normal", "high")
STATUSES = ("open", "in_progress", "waiting_user", "resolved", "closed")


def create_ticket(db: Session, user: User, data: dict) -> SupportTicket:
    require_permission(user, "ticket.write")
    if data.get("category") not in CATEGORIES:
        raise Invalid("Unknown category.")
    if data.get("priority", "normal") not in PRIORITIES:
        raise Invalid("Unknown priority.")
    ticket = SupportTicket(
        application_id=data["application_id"], reporter_id=user.id,
        summary=require_text(data.get("summary"), "The summary"),
        description=require_text(data.get("description"), "The description"),
        category=data["category"], priority=data.get("priority", "normal"),
    )
    db.add(ticket)
    db.flush()
    audit.record(db, user, "create", "support_ticket", ticket.id, ticket.code, new=row_dict(ticket))
    return ticket


def update_ticket(db: Session, user: User, ticket: SupportTicket, data: dict) -> SupportTicket:
    require_permission(user, "ticket.manage")
    if ticket.status == "closed":
        raise Conflict("A closed ticket cannot be changed.")
    before = row_dict(ticket)
    if "status" in data:
        if data["status"] not in STATUSES:
            raise Invalid("Unknown status.")
        if data["status"] in ("resolved", "closed") and not (data.get("resolution") or ticket.resolution):
            raise Invalid("Write down the resolution before you resolve or close a ticket.")
        ticket.status = data["status"]
        if data["status"] in ("resolved", "closed") and ticket.resolved_at is None:
            ticket.resolved_at = utcnow()
    for key in ("assignee_id", "priority", "category", "resolution"):
        if key in data:
            setattr(ticket, key, data[key])
    if "change_id" in data:
        if data["change_id"] is not None:
            change = db.get(ChangeRequest, data["change_id"])
            if change is None or change.application_id != ticket.application_id:
                raise Invalid("The change request must belong to the same application.")
        ticket.change_id = data["change_id"]
    if ticket.assignee_id and ticket.status == "open":
        ticket.status = "in_progress"
    db.flush()
    old, new = audit.changed_fields(before, row_dict(ticket))
    if new:
        audit.record(db, user, "update", "support_ticket", ticket.id, ticket.code, old, new)
    return ticket


def add_comment(db: Session, user: User, ticket: SupportTicket, body: str) -> TicketComment:
    require_permission(user, "ticket.write")
    if ticket.status == "closed":
        raise Conflict("A closed ticket cannot be commented.")
    comment = TicketComment(ticket_id=ticket.id, author_id=user.id, body=require_text(body, "The comment", 2))
    db.add(comment)
    db.flush()
    ticket.updated_at = utcnow()
    audit.record(db, user, "comment", "support_ticket", ticket.id, ticket.code, new={"comment": comment.body})
    return comment
