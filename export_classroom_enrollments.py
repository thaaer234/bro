# -*- coding: utf-8 -*-
import os
import sys
import django
import json

# إعداد الترميز لترميز UTF-8 لتفادي أخطاء الطباعة في ويندوز
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

# ضبط إعدادات Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from classroom.models import Classroom, Classroomenrollment

def main():
    print("=" * 70)
    print("تصدير بيانات انضمام طلاب الشعب غير المخفية إلى ملف JSON")
    print("=" * 70)

    # جلب الشعب غير المخفية والنشطة
    classrooms = Classroom.objects.filter(is_visible=True, is_active=True)
    print(f"تم العثور على {classrooms.count()} شعبة غير مخفية.")

    enrollments_data = []
    total_exported = 0

    for c in classrooms:
        # جلب الطلاب المسجلين في الشعبة
        enrollments = Classroomenrollment.objects.filter(classroom=c).select_related('student')
        print(f" - الشعبة: {c.name} (ID: {c.id}) | عدد الطلاب: {enrollments.count()}")
        
        for env in enrollments:
            student = env.student
            if student:
                enrollments_data.append({
                    'full_name': student.full_name,
                    'phone': student.phone,
                    'classroom_id': c.id,
                    'classroom_name': c.name
                })
                total_exported += 1

    # حفظ البيانات في ملف JSON
    output_filename = "classroom_enrollments.json"
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(enrollments_data, f, ensure_ascii=False, indent=4)

    print("=" * 70)
    print(f"تم بنجاح تصدير {total_exported} تسجيل طالب إلى الملف: {output_filename}")
    print("=" * 70)

if __name__ == '__main__':
    main()
