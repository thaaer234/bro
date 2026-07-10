"""
Site-wide formatting template tags and filters
Provides comma-separated number formatting across the entire site
"""

from django import template
from django.utils.safestring import mark_safe
from decimal import Decimal, InvalidOperation
import locale

register = template.Library()


@register.filter(is_safe=True)
def floatformat(value, arg=-1):
    """
    Override Django's built-in floatformat to always output
    standard formatting: dot for decimal, comma for thousands.
    Example: 1200000 → 1,200,000  |  1200000.50 → 1,200,000.50
    """
    if value is None or value == '':
        return ''

    try:
        if isinstance(value, str):
            # handle strings that may already contain commas
            value = value.replace(',', '')
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return str(value)

    try:
        decimals = int(arg)
    except (ValueError, TypeError):
        decimals = -1

    # negative arg = show decimals only when present (Django convention)
    if decimals < 0:
        decimals = abs(decimals)
        if d == d.to_integral_value():
            decimals = 0

    # format with Python f-string (always uses dot & comma)
    number_float = float(d)
    if decimals == 0:
        formatted = f"{number_float:,.0f}"
    else:
        formatted = f"{number_float:,.{decimals}f}"

    return formatted


@register.filter
def intcomma(value, use_l10n=True):
    """
    Convert an integer to a string containing commas every three digits.
    For example, 3000 becomes '3,000' and 45000 becomes '45,000'.
    """
    if value is None:
        return ''
    
    try:
        # Convert to float first to handle Decimal values
        if isinstance(value, Decimal):
            value = float(value)
        elif isinstance(value, str):
            value = float(value)
        
        # Format with commas
        formatted = f"{value:,.2f}"
        
        # Remove unnecessary decimal places if it's a whole number
        if formatted.endswith('.00'):
            formatted = formatted[:-3]
        
        return formatted
    except (ValueError, TypeError):
        return str(value)


@register.filter
def currency(value, currency_symbol=''):
    """
    Format a number as currency with comma separators
    """
    if value is None:
        return ''
    
    try:
        if isinstance(value, Decimal):
            value = float(value)
        elif isinstance(value, str):
            value = float(value)
        
        formatted = f"{value:,.2f}"
        
        if currency_symbol:
            return f"{currency_symbol} {formatted}"
        
        return formatted
    except (ValueError, TypeError):
        return str(value)


@register.filter
def percentage(value, decimals=2):
    """
    Format a number as percentage with comma separators
    """
    if value is None:
        return ''
    
    try:
        if isinstance(value, Decimal):
            value = float(value)
        elif isinstance(value, str):
            value = float(value)
        
        formatted = f"{value:,.{decimals}f}"
        return f"{formatted}%"
    except (ValueError, TypeError):
        return str(value)


@register.filter
def number_format(value, decimals=2):
    """
    Format a number with specified decimal places and comma separators
    """
    if value is None:
        return ''
    
    try:
        if isinstance(value, Decimal):
            value = float(value)
        elif isinstance(value, str):
            value = float(value)
        
        return f"{value:,.{decimals}f}"
    except (ValueError, TypeError):
        return str(value)


@register.simple_tag
def format_number(value, decimals=2, show_currency=False, currency_symbol=''):
    """
    Template tag to format numbers with commas and optional currency symbol
    """
    if value is None:
        return ''
    
    try:
        if isinstance(value, Decimal):
            value = float(value)
        elif isinstance(value, str):
            value = float(value)
        
        formatted = f"{value:,.{decimals}f}"
        
        if show_currency and currency_symbol:
            return f"{currency_symbol} {formatted}"
        
        return formatted
    except (ValueError, TypeError):
        return str(value)


@register.filter
def safe_intcomma(value):
    """
    Safe version of intcomma that handles None values gracefully
    """
    if value is None or value == '':
        return '0'
    return intcomma(value)


@register.filter
def financial_format(value):
    """
    Format financial values with proper comma separators
    """
    if value is None:
        return '0.00'
    
    try:
        if isinstance(value, Decimal):
            value = float(value)
        elif isinstance(value, str):
            value = float(value)
        
        # Always show 2 decimal places for financial values
        return f"{value:,.2f}"
    except (ValueError, TypeError):
        return '0.00'

