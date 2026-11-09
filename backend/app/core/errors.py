class DomainError(Exception):
    """A business rule was broken. The API turns it into an HTTP error with a plain message."""

    status_code = 409

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFound(DomainError):
    status_code = 404


class Forbidden(DomainError):
    status_code = 403


class Unauthorized(DomainError):
    status_code = 401


class Conflict(DomainError):
    status_code = 409


class Invalid(DomainError):
    status_code = 422
