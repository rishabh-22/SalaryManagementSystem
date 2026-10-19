"""Domain errors raised by services; mapped to HTTP responses in app.main."""


class DomainError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(DomainError):
    """404"""


class ConflictError(DomainError):
    """409"""


class BusinessRuleError(DomainError):
    """400"""


class UnprocessableError(DomainError):
    """422 in FastAPI's default validation error shape."""

    def __init__(self, loc: list[str | int], message: str) -> None:
        super().__init__(message)
        self.loc = loc
