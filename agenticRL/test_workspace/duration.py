"""Small duration-formatting utility."""


def format_duration(total_seconds: int) -> str:
    """Return a compact representation of a non-negative number of seconds."""
    if total_seconds < 0:
        raise ValueError("total_seconds must be non-negative")

    # BUG: this treats all seconds after the first hour as seconds, rather than
    # splitting them into a minute component and a remaining-second component.
    hours = total_seconds // 3600
    minutes = total_seconds // 60
    seconds = total_seconds % 60

    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"
