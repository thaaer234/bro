from django import template

register = template.Library()

@register.filter
def split(value, delimiter=','):
    """Split a string by delimiter"""
    if value:
        return value.split(delimiter)
    return []

@register.filter
def default_if_none(value, default=''):
    """Return default if value is None"""
    return value if value is not None else default

@register.filter
def multiply(value, arg):
    """Multiply two values"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def seconds_to_hhmm(value):
    """Format seconds as HH:MM."""
    try:
        total_seconds = int(value or 0)
    except (TypeError, ValueError):
        return "00:00"
    hours, remainder = divmod(max(total_seconds, 0), 3600)
    minutes = remainder // 60
    return f"{hours:02d}:{minutes:02d}"
