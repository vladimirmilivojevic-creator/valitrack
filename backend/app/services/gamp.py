"""GAMP 5 software categories and what they mean for the amount of testing.

GAMP 5 (second edition) keeps four categories for software:
1 infrastructure, 3 non-configured product, 4 configured product, 5 custom application.
The more an application is configured or custom-built, the more of it must be tested by us.
"""

GAMP_CATEGORIES: dict[int, dict] = {
    1: {
        "name": "Infrastructure software",
        "examples": "Operating systems, databases, network tools",
        "required_tests": ("IQ",),
        "summary": "Standard infrastructure. Prove it is installed correctly (IQ).",
    },
    3: {
        "name": "Non-configured product",
        "examples": "Off-the-shelf software used as delivered",
        "required_tests": ("IQ", "OQ"),
        "summary": "Used as delivered. Prove the installation (IQ) and that the functions we use work (OQ).",
    },
    4: {
        "name": "Configured product",
        "examples": "Quality, document or training systems that we configure to our processes",
        "required_tests": ("IQ", "OQ", "PQ"),
        "summary": "We configure it. Test the installation (IQ), the configured functions (OQ) "
        "and the real process end to end (PQ).",
    },
    5: {
        "name": "Custom application",
        "examples": "Spreadsheets with macros, scripts, in-house software",
        "required_tests": ("IQ", "OQ", "PQ"),
        "summary": "Built for us. Full lifecycle: specification, review of the design, IQ, OQ and PQ.",
    },
}

TEST_TYPE_MEANING = {
    "IQ": "Installation Qualification: is it installed and set up as specified?",
    "OQ": "Operational Qualification: does each function work as specified?",
    "PQ": "Performance Qualification: does it work for the real process and users?",
}


def required_test_types(category: int) -> tuple[str, ...]:
    return GAMP_CATEGORIES[category]["required_tests"]


def validation_approach(category: int, risk_class: str) -> str:
    """Plain-English rationale shown in the application page and in the report."""
    info = GAMP_CATEGORIES[category]
    effort = {
        "high": "The intended use is high risk, so every requirement needs a scripted test "
        "and tests of high-risk requirements are reviewed by QA.",
        "medium": "The intended use is medium risk, so every requirement needs a test; "
        "QA reviews the tests of high-risk requirements.",
        "low": "The intended use is low risk, so the effort is kept proportionate: "
        "every requirement still needs a test, and low-risk ones may use unscripted testing.",
    }[risk_class]
    return f"GAMP category {category} ({info['name']}). {info['summary']} {effort}"
