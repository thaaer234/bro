from django import template

register = template.Library()

@register.filter
def sum_attr(sequence, attr):
    """مجموع خاصية في تسلسل"""
    return sum(getattr(item, attr, 0) for item in sequence)