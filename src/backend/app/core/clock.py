"""Where the app gets the current time.

Code takes the time from a Clock instead of calling datetime.now(), so tests
can set it. A route asks for the clock with Depends(get_clock), and a test
sets the time with app.dependency_overrides[get_clock].
"""

from collections.abc import Callable
from datetime import UTC, datetime

# A function that returns the current time, with its time zone.
Clock = Callable[[], datetime]


def system_clock() -> datetime:
    """The real current time, in UTC."""
    return datetime.now(UTC)


def get_clock() -> Clock:
    """FastAPI dependency that gives a route the clock."""
    return system_clock
