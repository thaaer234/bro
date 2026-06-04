# -*- coding: utf-8 -*-
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
import django
django.setup()

from django.db import transaction
from django.core.exceptions import ValidationError
from accounts.models import Course
from quick.models import AcademicYear
from classroom.models import Classroom, Classroomenrollment
from students.models import Student

def run_test():
    print("🚀 بدء الفحص المالي والإداري للشعب...")
    
    # استخدام معاملة للتراجع عن أي تغييرات بعد الاختبار
    try:
        with transaction.atomic():
            # 1. تهيئة البيانات الأساسية
            academic_year, _ = AcademicYear.objects.get_or_create(
                name="سنة اختبارية",
                defaults={'start_date': '2026-01-01', 'end_date': '2026-12-31'}
            )
            
            course_a, _ = Course.objects.get_or_create(
                name="دورة اختبارية أ",
                defaults={'price': 10000, 'academic_year': academic_year}
            )
            course_b, _ = Course.objects.get_or_create(
                name="دورة اختبارية ب",
                defaults={'price': 15000, 'academic_year': academic_year}
            )
            
            classroom_a1 = Classroom.objects.create(
                name="شعبة أ1",
                class_type="study",
                branches="علمي",
                course=course_a
            )
            classroom_a2 = Classroom.objects.create(
                name="شعبة أ2",
                class_type="study",
                branches="علمي",
                course=course_a
            )
            classroom_b = Classroom.objects.create(
                name="شعبة ب",
                class_type="study",
                branches="علمي",
                course=course_b
            )
            
            student, _ = Student.objects.get_or_create(
                full_name="طالب اختباري للتجربة",
                defaults={'academic_year': academic_year, 'branch': 'علمي', 'student_number': 'TEST-9999'}
            )
            
            print(f"✅ تم إنشاء الطالب: {student.full_name}")
            
            # الاختبار الأول: تسجيل الطالب في الشعبة أ1 للدورة أ
            enrollment1 = Classroomenrollment(student=student, classroom=classroom_a1)
            enrollment1.full_clean()
            enrollment1.save()
            print("✅ الاختبار الأول: تم إضافة الطالب للشعبة (أ1) للدورة الأولى بنجاح.")
            
            # الاختبار الثاني: محاولة تسجيل الطالب في شعبة أخرى (ب) تابعة لدورة أخرى (ب)
            try:
                enrollment2 = Classroomenrollment(student=student, classroom=classroom_b)
                enrollment2.full_clean()
                enrollment2.save()
                print("✅ الاختبار الثاني: تم إضافة الطالب لشعبة ثانية (ب) تابعة لدورة ثانية بنجاح! (هذا ما قمت بطلبه وعمل بنجاح)")
            except ValidationError as e:
                print(f"❌ فشل الاختبار الثاني: لم يسمح النظام بإضافة الطالب لشعبة دورة ثانية. خطأ: {e}")
                raise AssertionError("التحقق منع التسجيل في شعبتين لدورتين مختلفتين!")
            
            # الاختبار الثالث: محاولة تسجيل الطالب في شعبة ثانية (أ2) تابعة لنفس الدورة الأولى (أ)
            try:
                enrollment3 = Classroomenrollment(student=student, classroom=classroom_a2)
                enrollment3.full_clean()
                enrollment3.save()
                print("❌ فشل الاختبار الثالث: سمح النظام للطالب بالتسجيل في شعبتين لنفس الدورة! (يجب أن يمنع ذلك)")
                raise AssertionError("التحقق سمح بالتسجيل في شعبتين لنفس الدورة!")
            except ValidationError as e:
                print(f"✅ الاختبار الثالث: منع النظام بنجاح تسجيل الطالب في شعبة أخرى لنفس الدورة. الرسالة: {e.messages[0]}")
                
            # إثارة خطأ متعمد لإلغاء المعاملة وعدم حفظ بيانات الاختبار في قاعدة البيانات
            raise RuntimeError("تراجع - كل شيء سليم تماماً!")
            
    except RuntimeError as e:
        if str(e) == "تراجع - كل شيء سليم تماماً!":
            print("\n🎉 الفحص تم بنجاح تام! التعديل يعمل بدقة 100% كما طلبت.")
        else:
            raise

if __name__ == "__main__":
    run_test()
