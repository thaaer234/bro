"""
Django Template Tags for Number Formatter Integration
Automatically applies number formatting to form fields
"""

from django import template
from django.forms import widgets
from django.utils.safestring import mark_safe
import json

register = template.Library()


@register.filter
def add_number_formatting(field, options=None):
    """
    Add number formatting attributes to a form field
    Usage: {{ field|add_number_formatting }}
    Usage: {{ field|add_number_formatting:"currency" }}
    """
    if not hasattr(field, 'field') or not hasattr(field.field, 'widget'):
        return field
    
    widget = field.field.widget
    
    # Default options based on field type
    default_options = {
        'thousandSeparator': ',',
        'decimalSeparator': '.',
        'decimalPlaces': 2,
        'allowNegative': True,
        'autoFormat': True
    }
    
    # Apply specific formatting based on options
    if options == 'currency':
        default_options.update({
            'prefix': 'ريال',
            'decimalPlaces': 2
        })
    elif options == 'integer':
        default_options.update({
            'decimalPlaces': 0
        })
    elif options == 'percentage':
        default_options.update({
            'suffix': '%',
            'decimalPlaces': 2
        })
    
    # Add data attributes to the widget
    if hasattr(widget, 'attrs'):
        widget.attrs.update({
            'data-number-format': 'true',
            'data-thousand-separator': default_options['thousandSeparator'],
            'data-decimal-separator': default_options['decimalSeparator'],
            'data-decimal-places': str(default_options['decimalPlaces']),
            'data-allow-negative': str(default_options['allowNegative']).lower(),
            'data-prefix': default_options.get('prefix', ''),
            'data-suffix': default_options.get('suffix', ''),
        })
    
    return field


@register.simple_tag
def number_formatter_init():
    """
    Generate JavaScript initialization code for number formatters
    Usage: {% number_formatter_init %}
    """
    return mark_safe('''
    <script>
    document.addEventListener('DOMContentLoaded', function() {
        // Initialize all elements with data-number-format attribute
        const elements = document.querySelectorAll('[data-number-format]');
        
        elements.forEach(element => {
            const options = {};
            
            // Parse options from data attributes
            if (element.dataset.thousandSeparator) {
                options.thousandSeparator = element.dataset.thousandSeparator;
            }
            if (element.dataset.decimalSeparator) {
                options.decimalSeparator = element.dataset.decimalSeparator;
            }
            if (element.dataset.decimalPlaces) {
                options.decimalPlaces = parseInt(element.dataset.decimalPlaces);
            }
            if (element.dataset.allowNegative) {
                options.allowNegative = element.dataset.allowNegative === 'true';
            }
            if (element.dataset.prefix) {
                options.prefix = element.dataset.prefix;
            }
            if (element.dataset.suffix) {
                options.suffix = element.dataset.suffix;
            }
            
            // Initialize formatter
            if (window.NumberFormatter) {
                new window.NumberFormatter(element, options);
            }
        });
    });
    </script>
    ''')


@register.simple_tag
def number_formatter_scripts():
    """
    Include the number formatter CSS and JS files
    Usage: {% number_formatter_scripts %}
    """
    return mark_safe('''
    <link rel="stylesheet" href="{% load static %}{% static 'css/number-formatter.css' %}">
    <script src="{% load static %}{% static 'js/number-formatter.js' %}"></script>
    ''')


@register.inclusion_tag('accounts/templatetags/number_input.html')
def number_input(field_name, value='', placeholder='', css_class='form-control', options=None):
    """
    Render a number input with automatic formatting
    Usage: {% number_input "amount" value=form.amount.value options="currency" %}
    """
    # Default options
    default_options = {
        'thousandSeparator': ',',
        'decimalSeparator': '.',
        'decimalPlaces': 2,
        'allowNegative': True,
        'autoFormat': True
    }
    
    # Apply specific formatting
    if options == 'currency':
        default_options.update({
            'prefix': 'ريال',
            'decimalPlaces': 2
        })
    elif options == 'integer':
        default_options.update({
            'decimalPlaces': 0
        })
    elif options == 'percentage':
        default_options.update({
            'suffix': '%',
            'decimalPlaces': 2
        })
    
    return {
        'field_name': field_name,
        'value': value,
        'placeholder': placeholder,
        'css_class': css_class,
        'options': default_options
    }


@register.filter
def format_number_input(field, format_type='default'):
    """
    Format a form field for number input with specific formatting
    Usage: {{ field|format_number_input:"currency" }}
    """
    if not hasattr(field, 'field'):
        return field
    
    widget = field.field.widget
    
    # Add CSS class
    if hasattr(widget, 'attrs'):
        widget.attrs['class'] = widget.attrs.get('class', '') + ' number-input'
        
        if format_type == 'currency':
            widget.attrs['class'] += ' currency-input'
            widget.attrs['data-currency'] = 'true'
        elif format_type == 'integer':
            widget.attrs['class'] += ' integer-input'
        elif format_type == 'percentage':
            widget.attrs['class'] += ' percentage-input'
    
    return field


@register.simple_tag
def auto_format_inputs():
    """
    Automatically format all number inputs on the page
    Usage: {% auto_format_inputs %}
    """
    return mark_safe('''
    <script>
    document.addEventListener('DOMContentLoaded', function() {
        // Auto-format all number inputs
        const numberInputs = document.querySelectorAll('input[type="number"], input.number-input');
        numberInputs.forEach(input => {
            if (!input.dataset.numberFormat) {
                input.dataset.numberFormat = 'true';
                input.dataset.thousandSeparator = ',';
                input.dataset.decimalSeparator = '.';
                input.dataset.decimalPlaces = '2';
                input.dataset.allowNegative = 'true';
                
                if (window.NumberFormatter) {
                    new window.NumberFormatter(input);
                }
            }
        });
        
        // Auto-format currency inputs
        const currencyInputs = document.querySelectorAll('input.currency-input, input[data-currency]');
        currencyInputs.forEach(input => {
            if (!input.dataset.numberFormat) {
                input.dataset.numberFormat = 'true';
                input.dataset.thousandSeparator = ',';
                input.dataset.decimalSeparator = '.';
                input.dataset.decimalPlaces = '2';
                input.dataset.allowNegative = 'true';
                input.dataset.prefix = 'ريال';
                
                if (window.NumberFormatter) {
                    new window.NumberFormatter(input);
                }
            }
        });
    });
    </script>
    ''')
