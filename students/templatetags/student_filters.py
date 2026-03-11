from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()

@register.filter
def get_dict_value(dictionary, key):
    """الحصول على قيمة من القاموس باستخدام مفتاح"""
    if dictionary and isinstance(dictionary, dict):
        return dictionary.get(key, 0)
    return 0

@register.filter
def dict_key(dictionary, key):
    """Return the value for key from the provided mapping."""
    if dictionary and isinstance(dictionary, dict):
        return dictionary.get(key, 0)
    return 0

@register.filter
def list_sum(values):
    """جمع قائمة من القيم"""
    try:
        if values:
            return sum(values)
        return 0
    except:
        return 0


@register.filter
def clean_decimal(value):
    """Render decimal numbers without localization commas or trailing zeros."""
    if value in (None, ""):
        return ""

    try:
        if isinstance(value, Decimal):
            dec_value = value
        else:
            dec_value = Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError, TypeError):
        return str(value)

    text = format(dec_value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text == "-0":
        return "0"
    return text
