"""Errors the app raises on purpose when a request breaks a rule, and how
each refusal reaches the phone. create_app in app/main.py adds the two
handlers below to the app."""

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class DomainError(Exception):
    """A request the app understood but has to refuse.

    handle_domain_error sends any of these to the phone as
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


def handle_domain_error(_: Request, error: DomainError) -> JSONResponse:
    """Send any DomainError to the phone in the same shape."""
    return JSONResponse(
        status_code=error.status,
        content={"detail": {"code": error.code, "message": error.message}},
    )


def handle_validation_error(
    _: Request, error: RequestValidationError
) -> JSONResponse:
    """Send a request that doesn't fit its route as 422, like FastAPI does,
    but without the values that were sent.

    FastAPI's own handler sends each refused value back. Some can't be
    written as JSON, such as NaN in a body, so the phone would get a 500.
    """
    errors = [
        {key: value for key, value in found.items() if key != "input"}
        for found in error.errors()
    ]
    return JSONResponse(
        status_code=422, content={"detail": jsonable_encoder(errors)}
    )
