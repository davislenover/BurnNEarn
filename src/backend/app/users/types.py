"""What users hands to other modules.

These are read-only copies, never database rows, so another module can't
change the users table by accident.
"""

import uuid
from dataclasses import dataclass

from app.core.errors import DomainError

# The one built-in user of the PoC. Fixed, so the seed script and
# get_current_user always agree on who it is.
DEMO_USER_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")


@dataclass(frozen=True)
class CurrentUser:
    """The user a request comes from."""

    user_id: uuid.UUID


class NotAuthenticatedError(DomainError):
    code = "not_authenticated"
    message = "Sign in to continue."
    status = 401
