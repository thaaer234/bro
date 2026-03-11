from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum

def get_teacher_attendance_stats(teacher, date=None, year=None, month=None):
    """
    خدمة منفصلة لجلب إحصائيات حضور المدرس
    """
    from attendance.models import TeacherAttendance
    
    if date:
        attendance = TeacherAttendance.objects.filter(
            teacher=teacher,
            date=date,
            status='present'
        )
        return sum(att.total_sessions for att in attendance)
    
    if year and month:
        attendance = TeacherAttendance.objects.filter(
            teacher=teacher,
            date__year=year,
            date__month=month,
            status='present'
        )
        return sum(att.total_sessions for att in attendance)
    
    if year:
        attendance = TeacherAttendance.objects.filter(
            teacher=teacher,
            date__year=year,
            status='present'
        )
        return sum(att.total_sessions for att in attendance)
    
    return 0