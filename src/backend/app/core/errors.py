"""Errors the app raises on purpose when a request breaks a rule."""


class DomainError(Exception):
    """A request the app understood but has to refuse.

    The handler in app/main.py sends any of these to the phone as
    {"detail": {"code": ..., "message": ...}}. A new error is a new subclass:

        class InsufficientFundsError(DomainError):
            code = "insufficient_funds"
            message = "You don't have enough currency for this."
            status = 409
    """

    code = "domain_error"
    message = "This request could not be completed."
    status = 400

    def __init__(self, message: str | None = None) -> None:
        if message is not None:
            self.message = message
        super().__init__(self.message)
