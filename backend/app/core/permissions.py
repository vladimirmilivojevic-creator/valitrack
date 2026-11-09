"""Who may do what. One table, so it is easy to read, to test and to show in the UI."""

ROLES = {
    "admin": "IT administrator",
    "validation_engineer": "Validation engineer",
    "tester": "Tester / end user",
    "qa_manager": "QA manager",
    "system_owner": "System owner",
    "auditor": "Auditor (read only)",
}

DEPARTMENTS = (
    "IT",
    "Quality Assurance",
    "Regulatory Affairs",
    "Production",
    "R&D",
    "Customer Service",
)

PERMISSION_LABELS = {
    "user.manage": "Create and manage user accounts",
    "app.write": "Create and edit applications and versions",
    "req.write": "Write requirements and the risk assessment",
    "req.approve": "Approve the requirements baseline (URS)",
    "test.write": "Write test cases",
    "test.approve": "Approve test cases",
    "run.execute": "Execute tests and upload evidence",
    "run.review": "Review executed tests",
    "deviation.write": "Raise and work on deviations",
    "deviation.close": "Close or accept deviations",
    "change.create": "Request changes",
    "change.coordinate": "Start impact assessments and plan testing",
    "change.assess": "Give a department impact assessment",
    "change.approve": "Approve or reject changes",
    "change.release": "Release approved changes",
    "config.write": "Edit the configuration baseline",
    "training.manage": "Plan and complete training sessions",
    "ticket.write": "Create tickets and comment",
    "ticket.manage": "Assign and resolve tickets",
    "report.generate": "Generate validation reports",
    "report.approve": "Approve validation reports and release versions",
    "demo.reset": "Reset the demo data",
}

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "admin": {
        "user.manage", "app.write", "config.write", "training.manage", "ticket.write",
        "ticket.manage", "change.create", "change.assess", "demo.reset",
    },
    "validation_engineer": {
        "app.write", "req.write", "test.write", "run.execute", "deviation.write",
        "change.create", "change.coordinate", "change.assess", "config.write",
        "training.manage", "ticket.write", "ticket.manage", "report.generate",
    },
    "tester": {"run.execute", "deviation.write", "change.create", "ticket.write"},
    "qa_manager": {
        "req.approve", "test.approve", "run.review", "deviation.close", "change.create",
        "change.coordinate", "change.assess", "change.approve", "change.release",
        "ticket.write", "report.approve",
    },
    "system_owner": {"change.create", "change.assess", "change.approve", "ticket.write"},
    "auditor": set(),
}


def has_permission(role: str, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())


def permissions_for(role: str) -> list[str]:
    return sorted(ROLE_PERMISSIONS.get(role, set()))
