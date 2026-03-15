from datetime import datetime, date


_DATE_FORMATS = (
    "%Y-%m-%d",
    "%m-%d-%Y",
    "%m/%d/%Y",
    "%d-%m-%Y",
    "%d/%m/%Y",
)


def parse_date(value) -> date | None:
    """Parse a date string in any common format to a Python date object.

    Tries ISO format first, then falls back through common US/EU formats.
    Returns None if value is empty or no format matches.
    """
    if not value:
        return None
    if isinstance(value, date):
        return value
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    return None