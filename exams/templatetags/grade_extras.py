from django import template
from students.models import Student

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def get_student_name(student_id):
    try:
        student = Student.objects.get(id=student_id)
        return student.full_name
    except Student.DoesNotExist:
        return "غير معروف"