"""Risk assessment: severity x probability x detectability (a simple FMEA).

Each factor is rated 1 to 3. The product is the risk priority number (RPN, 1 to 27).
The database computes the same value in a generated column; a test compares the two,
so the rule exists in one agreed form.
"""

HIGH_FROM = 12
MEDIUM_FROM = 6

SEVERITY = {1: "Minor", 2: "Major", 3: "Critical"}
PROBABILITY = {1: "Unlikely", 2: "Possible", 3: "Likely"}
DETECTABILITY = {1: "Easy to detect", 2: "Might be missed", 3: "Hard to detect"}


def rpn(severity: int, probability: int, detectability: int) -> int:
    return severity * probability * detectability


def risk_level(severity: int | None, probability: int | None, detectability: int | None) -> str | None:
    if severity is None or probability is None or detectability is None:
        return None
    value = rpn(severity, probability, detectability)
    if value >= HIGH_FROM:
        return "high"
    if value >= MEDIUM_FROM:
        return "medium"
    return "low"


def application_risk_class(patient_safety: bool, product_quality: bool, data_integrity: bool) -> str:
    """Intended-use risk of a whole application (mirrors the generated column in the database)."""
    if patient_safety or (product_quality and data_integrity):
        return "high"
    if product_quality or data_integrity:
        return "medium"
    return "low"
