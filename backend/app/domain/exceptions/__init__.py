"""Domain exceptions."""


class DomainError(Exception):
    """Base domain error."""


class AlreadyInstalledError(DomainError):
    """Application already bootstrapped."""


class NotInstalledError(DomainError):
    """Application not installed yet."""


class AuthenticationError(DomainError):
    """Invalid credentials or inactive user."""


class AuthorizationError(DomainError):
    """Insufficient permissions."""


class PasswordChangeRequiredError(DomainError):
    """User must change password before continuing."""


class ValidationError(DomainError):
    """Domain validation failure."""


class NotFoundError(DomainError):
    """Entity not found."""
