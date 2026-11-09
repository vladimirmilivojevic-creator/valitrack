"""Request bodies. Responses are plain JSON built by api/serializers.py."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LoginIn(Body):
    username: str
    password: str


class PasswordChangeIn(Body):
    current_password: str
    new_password: str


class SignatureIn(Body):
    """Every signed action asks for the password again."""

    password: str
    comment: str | None = None


class ReasonIn(Body):
    reason: str


class UserCreate(Body):
    username: str
    full_name: str
    email: str
    role: str
    department: str
    password: str


class UserUpdate(Body):
    full_name: str | None = None
    email: str | None = None
    role: str | None = None
    department: str | None = None
    is_active: bool | None = None


class PasswordResetIn(Body):
    new_password: str


class ApplicationCreate(Body):
    name: str
    description: str
    vendor: str
    department: str
    owner_id: int
    gamp_category: int
    intended_use: str
    patient_safety_impact: bool = False
    product_quality_impact: bool = False
    data_integrity_impact: bool = False
    initial_version: str | None = None


class ApplicationUpdate(Body):
    description: str | None = None
    vendor: str | None = None
    department: str | None = None
    owner_id: int | None = None
    gamp_category: int | None = None
    intended_use: str | None = None
    patient_safety_impact: bool | None = None
    product_quality_impact: bool | None = None
    data_integrity_impact: bool | None = None
    status: str | None = None
    reason: str


class VersionCreate(Body):
    version: str
    release_notes: str | None = None


class AppUserIn(Body):
    user_id: int
    app_role: str = "user"


class AppUsersIn(Body):
    assignments: list[AppUserIn]


class RequirementCreate(Body):
    kind: str = "URS"
    parent_id: int | None = None
    title: str
    description: str
    severity: int | None = Field(default=None, ge=1, le=3)
    probability: int | None = Field(default=None, ge=1, le=3)
    detectability: int | None = Field(default=None, ge=1, le=3)


class RequirementUpdate(Body):
    title: str | None = None
    description: str | None = None
    severity: int | None = Field(default=None, ge=1, le=3)
    probability: int | None = Field(default=None, ge=1, le=3)
    detectability: int | None = Field(default=None, ge=1, le=3)
    reason: str


class StepIn(Body):
    action: str
    expected_result: str


class TestCaseCreate(Body):
    test_type: str
    title: str
    objective: str
    preconditions: str | None = None
    style: str = "scripted"
    steps: list[StepIn] = []
    requirement_ids: list[int] = []


class TestCaseUpdate(Body):
    title: str | None = None
    objective: str | None = None
    preconditions: str | None = None
    style: str | None = None
    steps: list[StepIn] | None = None
    reason: str


class LinksIn(Body):
    requirement_ids: list[int]


class RunStart(Body):
    test_case_id: int
    version_id: int
    change_request_id: int | None = None


class StepResultIn(Body):
    result: str
    actual_result: str | None = None
    comment: str | None = None


class DeviationCreate(Body):
    application_id: int
    app_version_id: int | None = None
    test_run_id: int | None = None
    title: str
    description: str
    severity: str = "minor"
    owner_id: int | None = None
    due_date: date | None = None


class DeviationUpdate(Body):
    title: str | None = None
    description: str | None = None
    severity: str | None = None
    root_cause: str | None = None
    impact: str | None = None
    corrective_action: str | None = None
    preventive_action: str | None = None
    owner_id: int | None = None
    due_date: date | None = None
    reason: str


class CloseIn(SignatureIn):
    comment: str


class ChangeCreate(Body):
    application_id: int
    title: str
    change_type: str
    business_need: str
    description: str
    priority: str = "normal"
    target_version: str
    planned_release_date: date | None = None
    affects_requirements: bool = False


class ChangeUpdate(Body):
    title: str | None = None
    change_type: str | None = None
    business_need: str | None = None
    description: str | None = None
    priority: str | None = None
    target_version: str | None = None
    planned_release_date: date | None = None
    affects_requirements: bool | None = None
    reason: str


class AssessmentStartIn(Body):
    departments: list[str] = []


class ImpactIn(Body):
    impact_level: str
    affects_validated_state: bool
    comment: str


class TestingStartIn(Body):
    test_case_ids: list[int] | None = None


class RejectIn(Body):
    password: str
    reason: str


class ConfigCreate(Body):
    name: str
    value: str
    description: str | None = None
    change_request_id: int | None = None


class ConfigUpdate(Body):
    value: str | None = None
    description: str | None = None
    change_request_id: int | None = None
    reason: str


class TrainingCreate(Body):
    application_id: int
    app_version_id: int
    title: str
    session_type: str
    trainer_id: int
    session_date: date
    duration_minutes: int = 60
    materials: str | None = None
    attendee_ids: list[int] = []


class TrainingComplete(Body):
    password: str
    attended_ids: list[int]


class TicketCreate(Body):
    application_id: int
    summary: str
    description: str
    category: str
    priority: str = "normal"


class TicketUpdate(Body):
    assignee_id: int | None = None
    status: str | None = None
    priority: str | None = None
    category: str | None = None
    resolution: str | None = None
    change_id: int | None = None


class CommentIn(Body):
    body: str
