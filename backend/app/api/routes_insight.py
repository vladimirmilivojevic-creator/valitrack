from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import Forbidden, NotFound
from app.core.permissions import (
    DEPARTMENTS,
    PERMISSION_LABELS,
    ROLE_PERMISSIONS,
    ROLES,
    has_permission,
)
from app.models import AuditEntry, User
from app.services import dashboard, demo_scheduler, gamp, reports, risk
from app.services.common import to_jsonable

router = APIRouter(prefix="/api", tags=["insight"])


# ---------------------------------------------------------------- health (used by the uptime monitor)

@router.get("/health")
def health():
    """No database access on purpose: the uptime monitor calls this every few minutes and must not keep a
    serverless database awake all day."""
    return {"status": "ok"}


@router.get("/health/db")
def health_db(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "reachable"}


# ---------------------------------------------------------------- reference data for the screens

@router.get("/meta")
def meta(_: User = Depends(current_user)):
    return {
        "departments": list(DEPARTMENTS),
        "roles": ROLES,
        "permission_labels": PERMISSION_LABELS,
        "role_permissions": {role: sorted(perms) for role, perms in ROLE_PERMISSIONS.items()},
        "gamp": {str(k): {**v, "required_tests": list(v["required_tests"])} for k, v in gamp.GAMP_CATEGORIES.items()},
        "test_types": gamp.TEST_TYPE_MEANING,
        "risk": {
            "high_from": risk.HIGH_FROM, "medium_from": risk.MEDIUM_FROM,
            "severity": risk.SEVERITY, "probability": risk.PROBABILITY, "detectability": risk.DETECTABILITY,
        },
        "demo_mode": get_settings().demo_mode,
    }


@router.get("/demo/accounts")
def demo_accounts(db: Session = Depends(get_db)):
    """Shown on the login page of the public demo only."""
    if not get_settings().demo_mode:
        return {"enabled": False, "accounts": []}
    from app.seed.demo import DEMO_LOGINS, DEMO_PASSWORD

    users = {u.username: u for u in db.scalars(select(User).where(User.username.in_(list(DEMO_LOGINS))))}
    accounts = [
        {"username": name, "full_name": users[name].full_name, "role": users[name].role,
         "role_label": ROLES[users[name].role], "hint": hint}
        for name, hint in DEMO_LOGINS.items() if name in users
    ]
    return {"enabled": True, "password": DEMO_PASSWORD, "accounts": accounts}


@router.post("/demo/reset")
def demo_reset(x_reset_token: str | None = Header(default=None)):
    """Wipe the demo and load the sample data again. Only exists in demo mode.

    The work runs in its own thread and the answer comes at once. (The app also resets itself every night.)
    """
    settings = get_settings()
    if not settings.demo_mode:
        raise NotFound("This is not a demo installation.")
    if not (settings.demo_reset_token and x_reset_token == settings.demo_reset_token):
        raise Forbidden("The reset token is missing or wrong.")
    demo_scheduler.start_reset_in_background()
    return {"status": "started"}


@router.get("/demo/reset-allowed")
def demo_reset_allowed(user: User = Depends(current_user)):
    return {"allowed": get_settings().demo_mode and has_permission(user.role, "demo.reset")}


# ---------------------------------------------------------------- dashboard and SQL reports

@router.get("/dashboard")
def get_dashboard(_: User = Depends(current_user), db: Session = Depends(get_db)):
    return dashboard.build_dashboard(db)


@router.get("/reports")
def list_reports(_: User = Depends(current_user)):
    return reports.catalog()


@router.get("/reports/{key}")
def get_report(key: str, _: User = Depends(current_user), db: Session = Depends(get_db)):
    return reports.run_report(db, key)


@router.get("/reports/{key}/csv")
def get_report_csv(key: str, _: User = Depends(current_user), db: Session = Depends(get_db)):
    report = reports.run_report(db, key)
    body = reports.to_csv(report["columns"], report["rows"])
    return Response(body, media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="valitrack-{key}.csv"'})


# ---------------------------------------------------------------- audit trail

def _audit_query(entity_type, entity_id, actor, action, q, date_from, date_to):
    query = select(AuditEntry)
    if entity_type:
        query = query.where(AuditEntry.entity_type == entity_type)
    if entity_id:
        query = query.where(AuditEntry.entity_id == entity_id)
    if actor:
        query = query.where(AuditEntry.actor_name.ilike(f"%{actor}%"))
    if action:
        query = query.where(AuditEntry.action == action)
    if q:
        query = query.where(AuditEntry.entity_label.ilike(f"%{q}%"))
    if date_from:
        query = query.where(AuditEntry.occurred_at >= datetime.combine(date_from, time.min))
    if date_to:
        query = query.where(AuditEntry.occurred_at < datetime.combine(date_to + timedelta(days=1), time.min))
    return query


def _entry_out(e: AuditEntry) -> dict:
    return to_jsonable({
        "seq": e.seq, "occurred_at": e.occurred_at, "actor_id": e.actor_id, "actor_name": e.actor_name,
        "action": e.action, "entity_type": e.entity_type, "entity_id": e.entity_id,
        "entity_label": e.entity_label, "old_values": e.old_values, "new_values": e.new_values,
        "reason": e.reason, "prev_hash": e.prev_hash, "entry_hash": e.entry_hash,
    })


@router.get("/audit")
def list_audit(entity_type: str | None = None, entity_id: str | None = None, actor: str | None = None,
               action: str | None = None, q: str | None = None, date_from: date | None = None,
               date_to: date | None = None, limit: int = 50, offset: int = 0,
               _: User = Depends(current_user), db: Session = Depends(get_db)):
    query = _audit_query(entity_type, entity_id, actor, action, q, date_from, date_to)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(AuditEntry.seq.desc()).limit(min(limit, 200)).offset(offset))
    return {"total": total, "items": [_entry_out(e) for e in rows]}


@router.get("/audit/verify")
def verify_audit(_: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.execute(text("SELECT entries, first_broken_seq, head_hash FROM verify_audit_chain()")).one()
    return {"entries": row.entries, "first_broken_seq": row.first_broken_seq, "head_hash": row.head_hash,
            "intact": row.first_broken_seq is None}


@router.get("/audit/export.csv")
def export_audit(entity_type: str | None = None, entity_id: str | None = None, actor: str | None = None,
                 action: str | None = None, q: str | None = None, date_from: date | None = None,
                 date_to: date | None = None, _: User = Depends(current_user), db: Session = Depends(get_db)):
    query = _audit_query(entity_type, entity_id, actor, action, q, date_from, date_to)
    rows = [_entry_out(e) for e in db.scalars(query.order_by(AuditEntry.seq).limit(5000))]
    columns = ["seq", "occurred_at", "actor_name", "action", "entity_type", "entity_id", "entity_label",
               "reason", "old_values", "new_values", "entry_hash"]
    body = reports.to_csv(columns, [[r[c] for c in columns] for r in rows])
    return Response(body, media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="valitrack-audit-trail.csv"'})
