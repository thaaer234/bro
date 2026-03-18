from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


def _arabic_score(text):
    return sum(1 for char in text if "\u0600" <= char <= "\u06FF")


@register.filter
def fix_arabic_text(value):
    """Repair common mojibake where UTF-8 Arabic was decoded incorrectly."""
    if value in (None, ""):
        return value

    text = str(value)
    if not any(char in text for char in ("ط", "ظ", "Ø", "Ù")):
        return text

    for wrong_encoding in ("cp1256", "latin1"):
        try:
            repaired = text.encode(wrong_encoding).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue

        if repaired != text and _arabic_score(repaired) > _arabic_score(text):
            return repaired

    return text

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
