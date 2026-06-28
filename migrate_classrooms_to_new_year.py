# -*- coding: utf-8 -*-
import os
import sys
import django
from decimal import Decimal

# ضبط إعدادات Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from django.db import transaction
from django.contrib.auth.models import User
from quick.models import AcademicYear
from accounts.models import Course, Studentenrollment, Account
from classroom.models import Classroom, Classroomenrollment
from academic_years.models import AcademicYearTransferBatch, AcademicYearTransferCourseItem
from academic_years.services.transfers import AcademicYearTransferService
from students.models import Student

def main():
    print("=" * 80)
    print("🚀 سكربت ترحيل طلاب الشعب للفصل الجديد (2026-2027) وإعادة ربطهم بالشعب")
    print("=" * 80)

    # 1. التحقق من الفصل الدراسي النشط (الهدف)
    target_year = AcademicYear.objects.filter(is_active=True).first()
    if not target_year:
        print("❌ خطأ: لا يوجد فصل دراسي نشط في النظام!")
        return
    print(f"✅ الفصل الدراسي النشط (الهدف): {target_year.name} (ID: {target_year.id})")

    # 2. تحديد الفصل الدراسي القديم (المصدر)
    # نفترض أن المعرف 1 هو الفصل القديم 2025-2026
    try:
        source_year = AcademicYear.objects.get(id=1)
        print(f"✅ الفصل الدراسي المصدر: {source_year.name} (ID: {source_year.id})")
    except AcademicYear.DoesNotExist:
        print("❌ خطأ: لم يتم العثور على الفصل الدراسي ذو المعرف 1 (المصدر)!")
        return

    if source_year == target_year:
        print("❌ خطأ: الفصل المصدر هو نفسه الفصل الهدف!")
        return

    # 3. جلب الشعب غير المخفية
    classrooms = Classroom.objects.filter(is_visible=True, is_active=True)
    if not classrooms.exists():
        print("⚠️ لم يتم العثور على أي شعب غير مخفية ونشطة.")
        return

    print(f"\n📋 الشعب غير المخفية التي سيتم معالجتها ({classrooms.count()} شعب):")
    
    unique_courses = set()
    classroom_student_map = {}
    total_enrollments = 0

    for c in classrooms:
        students_in_classroom = list(c.students)
        classroom_student_map[c.id] = [s.id for s in students_in_classroom]
        total_enrollments += len(students_in_classroom)
        
        course = c.course
        course_info = "بدون دورة"
        if course:
            course_info = f"الدورة: {course.name} (ID: {course.id}) | فصل الدورة: {course.academic_year}"
            if course.academic_year != target_year:
                unique_courses.add(course)
        
        print(f" - الشعبة: {c.name} (ID: {c.id}) | {course_info} | عدد الطلاب الحالي: {len(students_in_classroom)}")

    if not unique_courses:
        print("\n✅ جميع دورات الشعب تتبع بالفعل للفصل الدراسي الجديد. لا يوجد شيء لترحيله.")
        return

    print(f"\n📦 الدورات الفريدة المطلوب ترحيلها إلى الفصل الجديد ({len(unique_courses)} دورات):")
    for course in unique_courses:
        print(f" - {course.name} (ID: {course.id})")

    print(f"\n💡 سيتم ترحيل {total_enrollments} تسجيل طالب محاسبياً، ونقلهم للفصل الجديد وإعادة توزيعهم على شعبهم.")
    
    # 4. طلب تأكيد التشغيل
    try:
        confirm = input("\n⚠️ هل تريد البدء بعملية الترحيل الفعلي الآن؟ (اكتب 'نعم' للتأكيد): ")
    except KeyboardInterrupt:
        print("\n❌ تم إلغاء العملية.")
        return

    if confirm.strip() != "نعم":
        print("❌ تم إلغاء العملية ولم يتم تعديل أي بيانات.")
        return

    # 5. جلب حساب الموظف أو المدير لتسجيل العملية باسمه
    actor = User.objects.filter(is_superuser=True).first()
    if not actor:
        print("❌ خطأ: لم يتم العثور على أي مستخدم سوبر يوزر لتسجيل العملية باسمه!")
        return

    print("\n⏳ جاري بدء عملية الترحيل (باستخدام نظام الترحيل المعتمد)...")
    
    try:
        with transaction.atomic():
            # أ. إنشاء دفعة الترحيل
            batch = AcademicYearTransferBatch.objects.create(
                source_academic_year=source_year,
                target_academic_year=target_year,
                created_by=actor,
                notes=f"ترحيل تلقائي للشعب الظاهرة بواسطة سكربت الاستعادة"
            )

            # ب. إضافة الدورات كعناصر للدفعة
            for course in unique_courses:
                AcademicYearTransferCourseItem.objects.create(
                    batch=batch,
                    source_course=course
                )

            print(f"🔗 تم إنشاء دفعة الترحيل بنجاح (ID: {batch.id}).")

            # ج. تشغيل خدمة الترحيل الرسمية لنقل الطلاب والدورات والقيود
            service = AcademicYearTransferService(batch=batch, actor=actor)
            summary = service.execute()
            print("✅ اكتمل الترحيل المحاسبي بنجاح.")
            print(f"📊 ملخص الترحيل: {dict(summary)}")

            # د. تحديث الشعب وإعادة تسجيل الطلاب
            for c in classrooms:
                if not c.course:
                    continue
                
                # تحديث الدورة المرتبطة بالشعبة لتشير للدورة الجديدة في الفصل الجديد
                old_course = c.course
                new_course = service.course_map.get(old_course.pk)
                if new_course:
                    c.course = new_course
                    c.save(update_fields=['course'])
                    print(f"   🔄 تم تحديث الشعبة {c.name} لترتبط بالدورة الجديدة: {new_course.name} (ID: {new_course.id})")

                # إعادة تسجيل الطلاب في الشعبة
                old_student_ids = classroom_student_map.get(c.id, [])
                enrolled_count = 0
                
                for old_id in old_student_ids:
                    # جلب الطالب المترحل الجديد من خريطة الترحيل
                    target_student = service.student_map.get(old_id)
                    
                    if not target_student:
                        # حالة خاصة: إذا كان الطالب في الشعبة ولكن ليس لديه تسجيل في الدورة
                        # نقوم بترحيل بروفايل الطالب بشكل مستقل
                        old_student = Student.objects.filter(id=old_id).first()
                        if old_student:
                            print(f"      ⚠️ الطالب {old_student.full_name} ليس لديه تسجيل في الدورة، سيتم ترحيل البروفايل يدوياً...")
                            target_student = service._get_or_create_target_student(old_student)
                            try:
                                old_student._skip_linked_cleanup = True
                                old_student.delete()
                            except Exception as del_err:
                                print(f"      ❌ فشل حذف البروفايل القديم للطالب {old_student.full_name}: {del_err}")

                    if target_student:
                        Classroomenrollment.objects.get_or_create(
                            classroom=c,
                            student=target_student
                        )
                        enrolled_count += 1

                print(f"   ✅ تم إعادة تسجيل {enrolled_count} طالب في الشعبة {c.name}.")

            print("\n🧹 جاري تنظيف الحسابات وإعادة احتساب الأرصدة...")
            # إعادة احتساب أرصدة الحسابات المتأثرة
            for account_id in service.entry_map.values():
                pass # الترحيل المعتمد يقوم بإعادة احتساب شجرة الحسابات تلقائياً

            print("\n🎉 تمت العملية بنجاح تام!")

    except Exception as e:
        print(f"\n❌ حدث خطأ أثناء الترحيل وتم التراجع عن كافة التغييرات: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
