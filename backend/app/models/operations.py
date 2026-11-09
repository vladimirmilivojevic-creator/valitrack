from datetime import date, datetime

from sqlalchemy import FetchedValue, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class ChangeRequest(Base):
    __tablename__ = "change_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(Text, server_default=FetchedValue())
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    title: Mapped[str] = mapped_column(Text)
    change_type: Mapped[str] = mapped_column(Text)
    business_need: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(Text, default="normal")
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    target_version: Mapped[str] = mapped_column(Text)
    planned_release_date: Mapped[date | None] = mapped_column()
    affects_requirements: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(Text, default="draft")
    risk_level: Mapped[str | None] = mapped_column(Text)
    requires_revalidation: Mapped[bool | None] = mapped_column()
    target_version_id: Mapped[int | None] = mapped_column(ForeignKey("app_versions.id"))
    decision_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    released_at: Mapped[datetime | None] = mapped_column()

    impacts: Mapped[list["ChangeImpact"]] = relationship(
        order_by="ChangeImpact.id", cascade="all, delete-orphan", lazy="selectin"
    )


class ChangeImpact(Base):
    __tablename__ = "change_impacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    change_id: Mapped[int] = mapped_column(ForeignKey("change_requests.id"))
    department: Mapped[str] = mapped_column(Text)
    assessor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    impact_level: Mapped[str | None] = mapped_column(Text)
    affects_validated_state: Mapped[bool | None] = mapped_column()
    comment: Mapped[str | None] = mapped_column(Text)
    assessed_at: Mapped[datetime | None] = mapped_column()


class ChangeTestLink(Base):
    __tablename__ = "change_test_links"

    change_id: Mapped[int] = mapped_column(ForeignKey("change_requests.id"), primary_key=True)
    test_case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id"), primary_key=True)


class ConfigItem(Base):
    __tablename__ = "config_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    name: Mapped[str] = mapped_column(Text)
    value: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    last_change_request_id: Mapped[int | None] = mapped_column(ForeignKey("change_requests.id"))
    updated_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class TrainingSession(Base):
    __tablename__ = "training_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(Text, server_default=FetchedValue())
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    app_version_id: Mapped[int] = mapped_column(ForeignKey("app_versions.id"))
    title: Mapped[str] = mapped_column(Text)
    session_type: Mapped[str] = mapped_column(Text)
    trainer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    session_date: Mapped[date] = mapped_column()
    duration_minutes: Mapped[int] = mapped_column()
    materials: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="planned")
    completed_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class TrainingAttendee(Base):
    __tablename__ = "training_attendees"

    session_id: Mapped[int] = mapped_column(ForeignKey("training_sessions.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    attended: Mapped[bool | None] = mapped_column()


class TrainingRecord(Base):
    __tablename__ = "training_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    app_version_id: Mapped[int] = mapped_column(ForeignKey("app_versions.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    session_id: Mapped[int | None] = mapped_column(ForeignKey("training_sessions.id"))
    status: Mapped[str] = mapped_column(Text)
    required_at: Mapped[datetime | None] = mapped_column()
    completed_at: Mapped[datetime | None] = mapped_column()
    comment: Mapped[str | None] = mapped_column(Text)


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(Text, server_default=FetchedValue())
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    summary: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(Text, default="normal")
    status: Mapped[str] = mapped_column(Text, default="open")
    resolution: Mapped[str | None] = mapped_column(Text)
    change_id: Mapped[int | None] = mapped_column(ForeignKey("change_requests.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column()

    comments: Mapped[list["TicketComment"]] = relationship(
        order_by="TicketComment.id", cascade="all, delete-orphan", lazy="selectin"
    )


class TicketComment(Base):
    __tablename__ = "ticket_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("support_tickets.id"))
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
