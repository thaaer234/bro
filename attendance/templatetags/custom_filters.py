# attendance/templatetags/custom_filters.py
from django import template

register = template.Library()

@register.filter(name='get_attendance')
def get_attendance(dictionary, teacher_id):
    """الحصول على سجل الحضور للمدرس من القاموس"""
    if dictionary and isinstance(dictionary, dict):
        return dictionary.get(teacher_id)
    return None