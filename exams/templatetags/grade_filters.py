from django import template

register = template.Library()

@register.filter
def find_exam_type(forms, exam_type):
    """Find form with specific exam type"""
    for form in forms:
        if hasattr(form.instance, 'exam_type') and form.instance.exam_type == exam_type:
            return form
    return None

@register.filter
def default_if_none(value):
    """Return empty string if value is None"""
    return value if value is not None else ''

@register.filter
def mul(value, arg):
    """Multiply filter"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0