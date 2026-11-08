"""What trading hands to other modules: its refusals.

Each reaches the phone as {"detail": {"code": ..., "message": ...}} with
status 409. buy in service.py says when each is raised.
"""

from decimal import Decimal

from app.core.errors import DomainError


class RequestIdReusedError(DomainError):
    code = "request_id_reused"
    message = "This request ID was already used for a different trade."
    status = 409


class MarketClosedError(DomainError):
    code = "market_closed"
    message = "The market is closed. Try again when it opens."
    status = 409


class PriceOutOfDateError(DomainError):
    code = "price_out_of_date"
    message = (
        "This stock's price is out of date, so it can't be bought right now."
    )
    status = 409


class PriceChangedError(DomainError):
    """The price moved after the user saw it (SEC-29).

    It can only be made with the new price, which the message gives with 4
    decimals, so the phone can show it and ask the user to confirm again.
    """

    code = "price_changed"
    status = 409

    def __init__(self, price: Decimal) -> None:
        self.price = price
        super().__init__(
            f"The price is now {price:.4f}. Check it and confirm again."
        )
