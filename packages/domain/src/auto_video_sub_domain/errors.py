from __future__ import annotations


class DomainError(Exception):
    code = "DOMAIN_ERROR"
    status_code = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class AuthenticationError(DomainError):
    code = "AUTH_REQUIRED"
    status_code = 401


class AuthorizationError(DomainError):
    code = "AUTH_FORBIDDEN"
    status_code = 403


class NotFoundError(DomainError):
    code = "NOT_FOUND"
    status_code = 404


class ConflictError(DomainError):
    code = "CONFLICT"
    status_code = 409


class QuotaExceededError(DomainError):
    code = "QUOTA_EXCEEDED"
    status_code = 429

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class ValidationError(DomainError):
    code = "VALIDATION_ERROR"
    status_code = 422

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code
