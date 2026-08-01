"""Worker runtime exceptions."""


class LeaseOwnershipLost(RuntimeError):
    """Raised when a supervisor can no longer prove ownership of a bot."""
