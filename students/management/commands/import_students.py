import pandas as pd
import os
import django
import random
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from students.models import Student

def update_existing_students():
    print("🚀 بدء تحديث بيانات الطلاب الموجودين...")
    
    # قراءة البيانات من Excel
    df = pd.read_excel('Copy of بيانات الطلاب 26(1).xlsx', sheet_name='أدبي')
    
    updated_count = 0
    not_found_count = 0
    error_count = 0
    
    for index, row in df.iterrows():
        try:
            clean_name = clean_student_name(row['الاسم'])
            
            # البحث عن الطالب الموجود
            existing_student = find_student_by_name(clean_name)
            
            if existing_student:
                # تحديث البيانات
                update_student_data(
                    existing_student.id,
                    academic_level=row['المستوى الأكاديمي'],
                    registration_status=row['الحالة التسجيلية']
                )
                print(f"✅ تم تحديث: {clean_name}")
                updated_count += 1
            else:
                print(f"⚠️  غير موجود: {clean_name}")
                not_found_count += 1
                
        except Exception as e:
            print(f"❌ خطأ في {clean_name}: {str(e)}")
            error_count += 1
    
    print(f"\n🎉 النتيجة النهائية:")
    print(f"✅ تم تحديث: {updated_count} طالب")
    print(f"⚠️  غير موجود: {not_found_count} طالب")
    print(f"❌ أخطاء: {error_count} طالب")

# دالة البحث عن طالب بالاسم
def find_student_by_name(name):
    # ابحث في الداتابيز عن طالب بنفس الاسم
    students = Student.objects.filter(name=name)
    if students.exists():
        return students.first()
    return None

# دالة تحديث البيانات
def update_student_data(student_id, academic_level, registration_status):
    student = Student.objects.get(id=student_id)
    student.academic_level = academic_level
    student.registration_status = registration_status
    student.save()