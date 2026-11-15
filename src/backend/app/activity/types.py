"""Activity's refusals, sent using the app's existing error handler."""

from app.core.errors import DomainError


class ActivityDateOutOfRangeError(DomainError):
    code = "activity_date_out_of_range"
    message = "Activity dates must be today or one of the preceding six days."
    status = 422
