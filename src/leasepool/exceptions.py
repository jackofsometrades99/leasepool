class LeasePoolError(Exception):
    """Base exception for leasepool."""


class LeasePoolNotStartedError(LeasePoolError):
    """Raised when the manager has not been started."""


class LeaseUnavailableError(LeasePoolError):
    """Raised when no executor can be acquired."""


class LeaseExpiredError(LeasePoolError):
    """Raised when a lease has expired or has been revoked."""


class UnsupportedBackendError(LeasePoolError):
    """Raised when the selected executor backend is unavailable."""
