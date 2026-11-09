from datetime import date, datetime

from sqlalchemy import Computed, FetchedValue, ForeignKey, LargeBinary, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(Text, server_default=FetchedValue())
    name: Mapped[str] = mapped_column(Text, unique=True)
    description: Mapped[str] = mapped_column(Text)
    vendor: Mapped[str] = mapped_column(Text)
    department: Mapped[str] = mapped_column(Text)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    gamp_category: Mapped[int] = mapped_column()
    intended_use: Mapped[str] = mapped_column(Text)
    patient_safety_impact: Mapped[bool] = mapped_column(default=False)
    product_quality_impact: Mapped[bool] = mapped_column(default=False)
    data_integrity_impact: Mapped[bool] = mapped_column(default=False)
    risk_class: Mapped[str] = mapped_column(Text, Computed("NULL", persisted=True))
    status: Mapped[str] = mapped_column(Text, default="active")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    owner = relationship("User", lazy="joined")


class ApplicationUser(Base):
    __tablename__ = "application_users"

    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    app_role: Mapped[str] = mapped_column(Text, default="user")
    granted_at: Mapped[datetime] = mapped_column(server_default=func.now())


class AppVersion(Base):
    __tablename__ = "app_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    version: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="in_validation")
    urs_approved: Mapped[bool] = mapped_column(default=False)
    urs_baseline_hash: Mapped[str | None] = mapped_column(Text)
    urs_approved_at: Mapped[datetime | None] = mapped_column()
    release_notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    validated_at: Mapped[datetime | None] = mapped_column()


class Requirement(Base):
    __tablename__ = "requirements"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    code: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("requirements.id"))
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[int | None] = mapped_column()
    probability: Mapped[int | None] = mapped_column()
    detectability: Mapped[int | None] = mapped_column()
    rpn: Mapped[int | None] = mapped_column(Computed("NULL", persisted=True))
    risk_level: Mapped[str | None] = mapped_column(Text, Computed("NULL", persisted=True))
    status: Mapped[str] = mapped_column(Text, default="active")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class TestCase(Base):
    __tablename__ = "test_cases"
    __test__ = False  # not a pytest class

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    code: Mapped[str] = mapped_column(Text)
    test_type: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    objective: Mapped[str] = mapped_column(Text)
    preconditions: Mapped[str | None] = mapped_column(Text)
    style: Mapped[str] = mapped_column(Text, default="scripted")
    status: Mapped[str] = mapped_column(Text, default="draft")
    revision: Mapped[int] = mapped_column(default=1)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    steps: Mapped[list["TestStep"]] = relationship(
        order_by="TestStep.step_no", cascade="all, delete-orphan", lazy="selectin"
    )


class TestStep(Base):
    __tablename__ = "test_steps"
    __test__ = False

    id: Mapped[int] = mapped_column(primary_key=True)
    test_case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id"))
    step_no: Mapped[int] = mapped_column()
    action: Mapped[str] = mapped_column(Text)
    expected_result: Mapped[str] = mapped_column(Text)


class RequirementTestLink(Base):
    __tablename__ = "requirement_test_links"

    requirement_id: Mapped[int] = mapped_column(ForeignKey("requirements.id"), primary_key=True)
    test_case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id"), primary_key=True)


class TestRun(Base):
    __tablename__ = "test_runs"
    __test__ = False

    id: Mapped[int] = mapped_column(primary_key=True)
    test_case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id"))
    test_case_revision: Mapped[int] = mapped_column()
    app_version_id: Mapped[int] = mapped_column(ForeignKey("app_versions.id"))
    change_request_id: Mapped[int | None] = mapped_column(ForeignKey("change_requests.id"))
    status: Mapped[str] = mapped_column(Text, default="in_progress")
    result: Mapped[str | None] = mapped_column(Text)
    executed_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column()
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column()
    review_comment: Mapped[str | None] = mapped_column(Text)

    steps: Mapped[list["TestRunStep"]] = relationship(
        order_by="TestRunStep.step_no", cascade="all, delete-orphan", lazy="selectin"
    )


class TestRunStep(Base):
    __tablename__ = "test_run_steps"
    __test__ = False

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("test_runs.id"))
    step_no: Mapped[int] = mapped_column()
    action: Mapped[str] = mapped_column(Text)
    expected_result: Mapped[str] = mapped_column(Text)
    actual_result: Mapped[str | None] = mapped_column(Text)
    result: Mapped[str] = mapped_column(Text, default="pending")
    comment: Mapped[str | None] = mapped_column(Text)
    executed_at: Mapped[datetime | None] = mapped_column()


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_step_id: Mapped[int] = mapped_column(ForeignKey("test_run_steps.id"))
    filename: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column()
    sha256: Mapped[str] = mapped_column(Text)
    data: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    uploaded_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Deviation(Base):
    __tablename__ = "deviations"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(Text, server_default=FetchedValue())
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    app_version_id: Mapped[int | None] = mapped_column(ForeignKey("app_versions.id"))
    test_run_id: Mapped[int | None] = mapped_column(ForeignKey("test_runs.id"))
    source: Mapped[str] = mapped_column(Text, default="manual")
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(Text)
    root_cause: Mapped[str | None] = mapped_column(Text)
    impact: Mapped[str | None] = mapped_column(Text)
    corrective_action: Mapped[str | None] = mapped_column(Text)
    preventive_action: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    due_date: Mapped[date | None] = mapped_column()
    status: Mapped[str] = mapped_column(Text, default="open")
    closure_comment: Mapped[str | None] = mapped_column(Text)
    closed_at: Mapped[datetime | None] = mapped_column()
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class ReportDocument(Base):
    __tablename__ = "report_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    doc_number: Mapped[str] = mapped_column(Text, server_default=FetchedValue())
    app_version_id: Mapped[int] = mapped_column(ForeignKey("app_versions.id"))
    status: Mapped[str] = mapped_column(Text, default="draft")
    generated_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    generated_at: Mapped[datetime] = mapped_column(server_default=func.now())
    state_hash: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(Text)
    gate_passed: Mapped[bool] = mapped_column()
    pdf: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
