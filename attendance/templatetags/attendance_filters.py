from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """للحصول على قيمة من القاموس باستخدام مفتاح"""
    return dictionary.get(key)

@register.filter
def filter_status(queryset, status):
    """لتصفية الكويري سيت حسب الحالة"""
    return queryset.filter(status=status)

@register.filter
def present_count(queryset):
    """عد المدرسين الحاضرين"""
    return queryset.filter(status='present').count()

@register.filter
def total_sessions(queryset):
    """حساب إجمالي الجلسات الكاملة"""
    return sum(att.session_count for att in queryset if att.status == 'present')

@register.filter
def total_half_sessions(queryset):
    """حساب إجمالي أنصاف الجلسات"""
    return sum(att.half_session_count for att in queryset if att.status == 'present')

@register.filter
def total_combined_sessions(queryset):
    """حساب إجمالي الجلسات مع أنصاف الجلسات"""
    total = 0
    for att in queryset:
        if att.status == 'present':
            total += att.session_count + (att.half_session_count * 0.5)
    return total