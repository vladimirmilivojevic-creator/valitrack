from datetime import datetime

from sqlalchemy import BigInteger, FetchedValue, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(Text, unique=True)
    full_name: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    department: Mapped[str] = mapped_column(Text)
    password_hash: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True)
    failed_logins: Mapped[int] = mapped_column(default=0)
    locked_until: Mapped[datetime | None] = mapped_column()
    last_login_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ESignature(Base):
    """An electronic signature. The database stamps the time and the signature hash."""

    __tablename__ = "e_signatures"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    signer_name: Mapped[str] = mapped_column(Text)
    signer_role: Mapped[str] = mapped_column(Text)
    meaning: Mapped[str] = mapped_column(Text)
    entity_type: Mapped[str] = mapped_column(Text)
    entity_id: Mapped[int] = mapped_column(Integer)
    entity_label: Mapped[str] = mapped_column(Text)
    record_hash: Mapped[str] = mapped_column(Text)
    comment: Mapped[str | None] = mapped_column(Text)
    signed_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    signature_hash: Mapped[str] = mapped_column(Text, server_default=FetchedValue())


class AuditEntry(Base):
    """Read model of the append-only audit_log table (rows are written by the audit service)."""

    __tablename__ = "audit_log"

    seq: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column()
    actor_id: Mapped[int | None] = mapped_column(Integer)
    actor_name: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text)
    entity_type: Mapped[str] = mapped_column(Text)
    entity_id: Mapped[str] = mapped_column(Text)
    entity_label: Mapped[str | None] = mapped_column(Text)
    old_values: Mapped[dict | None] = mapped_column(JSONB)
    new_values: Mapped[dict | None] = mapped_column(JSONB)
    reason: Mapped[str | None] = mapped_column(Text)
    prev_hash: Mapped[str] = mapped_column(Text)
    entry_hash: Mapped[str] = mapped_column(Text)
