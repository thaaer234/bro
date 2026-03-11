def build_attendance_notification(attendance):
    status_label = attendance.get_status_display()
    title = "تسجيل حضور" if attendance.status == "present" else "تسجيل غياب"
    classroom_name = attendance.classroom.name if attendance.classroom else "الشعبة"
    message = f"الحالة: {status_label}، الشعبة: {classroom_name}، التاريخ: {attendance.date}"
    return title, message
