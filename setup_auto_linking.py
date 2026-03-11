# fix_branches_simple.py
import os
import django
import sys
import json
import ast

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from django.db.models import Q
from django.utils import timezone
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_teacher_branches_completely():
    """إصلاح كامل لبيانات الفروع - الإصدار النهائي"""
    from employ.models import Teacher
    
    print("🔧 الإصلاح الكامل لبيانات الفروع...")
    
    # خريطة الفروع الصحيحة
    branch_mapping = {
        # الفروع بالعربية
        'علمي': 'علمي',
        'أدبي': 'أدبي', 
        'تاسع': 'تاسع',
        'تمهيدي': 'تمهيدي',
        
        # الفروع بالإنجليزية
        'TOUCH': 'تمهيدي',
        'PREPARATORY': 'تمهيدي',
        'INNTH': 'تاسع',
        'FITFRARY': 'أدبي',
        'SCIENCE': 'علمي',
        'LITERARY': 'أدبي',
        'NINTH': 'تاسع',
        
        # التصحيعات الخاصة
        'Scientific': 'علمي',
        'Literary': 'أدبي',
        'Ninth': 'تاسع',
        'Preparatory': 'تمهيدي'
    }
    
    fixed_count = 0
    
    for teacher in Teacher.objects.all():
        original_branches = teacher.branches
        if not original_branches:
            continue
        
        print(f"🔍 معالجة: {teacher.full_name}")
        print(f"   البيانات الأصلية: {original_branches} (نوع: {type(original_branches)})")
        
        try:
            fixed_branches = []
            
            # إذا كانت البيانات نصاً
            if isinstance(original_branches, str):
                # تنظيف النص
                clean_text = original_branches.strip()
                
                # محاولة تحليل كقائمة
                if clean_text.startswith('[') and clean_text.endswith(']'):
                    try:
                        parsed_list = ast.literal_eval(clean_text)
                        if isinstance(parsed_list, list):
                            # معالجة كل عنصر في القائمة
                            for item in parsed_list:
                                if isinstance(item, str) and item.strip():
                                    clean_item = item.strip().replace("'", "").replace('"', '')
                                    mapped_branch = branch_mapping.get(clean_item, clean_item)
                                    if mapped_branch and mapped_branch not in fixed_branches:
                                        fixed_branches.append(mapped_branch)
                    except:
                        # إذا فشل التحليل، افصل بالفاصلة
                        items = clean_text.strip('[]').split(',')
                        for item in items:
                            if item.strip():
                                clean_item = item.strip().replace("'", "").replace('"', '')
                                mapped_branch = branch_mapping.get(clean_item, clean_item)
                                if mapped_branch and mapped_branch not in fixed_branches:
                                    fixed_branches.append(mapped_branch)
                else:
                    # إذا كانت نصاً عادياً
                    items = clean_text.split(',')
                    for item in items:
                        if item.strip():
                            clean_item = item.strip().replace("'", "").replace('"', '')
                            mapped_branch = branch_mapping.get(clean_item, clean_item)
                            if mapped_branch and mapped_branch not in fixed_branches:
                                fixed_branches.append(mapped_branch)
            
            # إذا كانت البيانات قائمة
            elif isinstance(original_branches, list):
                for item in original_branches:
                    if isinstance(item, str) and item.strip():
                        clean_item = item.strip().replace("'", "").replace('"', '')
                        mapped_branch = branch_mapping.get(clean_item, clean_item)
                        if mapped_branch and mapped_branch not in fixed_branches:
                            fixed_branches.append(mapped_branch)
            
            # إذا لم نتمكن من استخراج فروع صحيحة، نستخدم الاسم لتخمين الفرع
            if not fixed_branches:
                teacher_name = teacher.full_name.lower()
                if 'علمي' in teacher_name or 'science' in teacher_name or 'scientific' in teacher_name:
                    fixed_branches = ['علمي']
                elif 'أدبي' in teacher_name or 'literary' in teacher_name:
                    fixed_branches = ['أدبي']
                elif 'تاسع' in teacher_name or 'ninth' in teacher_name:
                    fixed_branches = ['تاسع']
                elif 'تمهيدي' in teacher_name or 'preparatory' in teacher_name:
                    fixed_branches = ['تمهيدي']
            
            # حفظ البيانات المصححة
            if fixed_branches:
                teacher.branches = fixed_branches
                teacher.save()
                fixed_count += 1
                print(f"   ✅ تم الإصلاح: {fixed_branches}")
            else:
                print(f"   ⚠ لم يتم العثور على فروع صحيحة")
                
        except Exception as e:
            print(f"   ❌ خطأ: {e}")
    
    print(f"\n✅ تم إصلاح {fixed_count} مدرس")
    return fixed_count

def assign_teachers_to_existing_courses():
    """تعيين المدرسين للدورات الموجودة بناءً على الفروع"""
    from accounts.models import Course, CourseTeacherAssignment
    from employ.models import Teacher
    
    print("\n🎯 تعيين المدرسين للدورات الموجودة...")
    
    # خريطة الربط بين الفروع والدورات الموجودة
    branch_course_mapping = {
        'علمي': ['علمي', 'دورة علمي', 'علمي 2025', 'دورة شتاء علمي'],
        'أدبي': ['أدبي', 'دورة أدبي', 'أدبي 2025', 'دورة شتاء أدبي'], 
        'تاسع': ['تاسع', 'دورة تاسع', 'تاسع 2025', 'دورة شتاء تاسع'],
        'تمهيدي': ['تمهيدي', 'دورة تمهيدي', 'تمهيدي 2025', 'دورة شتاء تمهيدي', 'تاتش', 'TOUCH']
    }
    
    assignment_count = 0
    
    for teacher in Teacher.objects.all():
        branches = teacher.branches or []
        
        if not branches:
            print(f"   ⚠ {teacher.full_name}: بدون فروع")
            continue
        
        # نأخذ الفرع الأول فقط لتجنب التكرار
        main_branch = branches[0] if branches else None
        
        if not main_branch:
            continue
            
        # البحث عن الكلمات الدلالية للفرع في أسماء الدورات
        course_keywords = branch_course_mapping.get(main_branch, [])
        
        if not course_keywords:
            print(f"   ⚠ {teacher.full_name}: لا توجد كلمات دلالية للفرع '{main_branch}'")
            continue
        
        # البحث عن الدورات المناسبة
        suitable_courses = Course.objects.filter(
            Q(name_ar__icontains=main_branch) | 
            Q(name__icontains=main_branch)
        )
        
        # إذا لم نجد، نبحث بالكلمات الدلالية
        if not suitable_courses.exists():
            for keyword in course_keywords:
                suitable_courses = Course.objects.filter(
                    Q(name_ar__icontains=keyword) | 
                    Q(name__icontains=keyword)
                )
                if suitable_courses.exists():
                    break
        
        if not suitable_courses.exists():
            print(f"   ⚠ {teacher.full_name}: لا توجد دورات مناسبة للفرع '{main_branch}'")
            continue
        
        assigned_courses = []
        
        for course in suitable_courses:
            # التحقق من عدم وجود تعيين مسبق
            exists = CourseTeacherAssignment.objects.filter(
                teacher=teacher,
                course=course
            ).exists()
            
            if not exists:
                CourseTeacherAssignment.objects.create(
                    teacher=teacher,
                    course=course,
                    start_date=timezone.now().date(),
                    is_active=True,
                    notes=f"تعيين تلقائي - فرع {main_branch}"
                )
                assignment_count += 1
                assigned_courses.append(course.name_ar or course.name)
                print(f"   ✅ {teacher.full_name} → {course.name_ar or course.name}")
            else:
                print(f"   ℹ {teacher.full_name}: التعيين موجود مسبقاً لـ {course.name_ar or course.name}")
        
        if assigned_courses:
            print(f"   📋 تم تعيين {teacher.full_name} في: {', '.join(assigned_courses)}")
    
    print(f"   ✅ تم إنشاء {assignment_count} تعيين جديد")
    return assignment_count

def link_teacher_attendance_to_courses():
    """ربط حضور المدرسين مع الدورات المناسبة"""
    from attendance.models import TeacherAttendance
    from employ.models import Teacher
    from accounts.models import Course, CourseTeacherAssignment
    
    print("\n📊 ربط حضور المدرسين مع الدورات...")
    
    linked_count = 0
    
    # جلب جميع سجلات حضور المدرسين
    teacher_attendances = TeacherAttendance.objects.all().select_related('teacher')
    
    for attendance in teacher_attendances:
        teacher = attendance.teacher
        branches = teacher.branches or []
        
        if not branches:
            print(f"   ⚠ {teacher.full_name}: بدون فروع - لا يمكن الربط")
            continue
        
        # نأخذ الفرع الأول
        main_branch = branches[0]
        
        # البحث عن الدورات المناسبة لهذا الفرع
        suitable_courses = Course.objects.filter(
            Q(name_ar__icontains=main_branch) | 
            Q(name__icontains=main_branch)
        )
        
        if not suitable_courses.exists():
            print(f"   ⚠ {teacher.full_name}: لا توجد دورات مناسبة للفرع '{main_branch}'")
            continue
        
        # التحقق من وجود تعيينات للمدرس في هذه الدورات
        assignments = CourseTeacherAssignment.objects.filter(
            teacher=teacher,
            course__in=suitable_courses
        )
        
        if assignments.exists():
            course_names = [ass.course.name_ar or ass.course.name for ass in assignments]
            print(f"   ✅ {teacher.full_name}: مرتبط مسبقاً مع {', '.join(course_names)}")
            linked_count += 1
        else:
            # إذا لم يكن هناك تعيين، ننشئ تعييناً تلقائياً للدورة الأولى
            course = suitable_courses.first()
            CourseTeacherAssignment.objects.create(
                teacher=teacher,
                course=course,
                start_date=timezone.now().date(),
                is_active=True,
                notes=f"تعيين تلقائي من سجل الحضور - فرع {main_branch}"
            )
            print(f"   ✅ {teacher.full_name}: تم ربطه تلقائياً مع {course.name_ar or course.name}")
            linked_count += 1
    
    print(f"   ✅ تم ربط {linked_count} مدرس مع دورات مناسبة")
    return linked_count

def show_existing_courses():
    """عرض الدورات الموجودة في النظام"""
    from accounts.models import Course
    
    print("\n📚 الدورات الموجودة في النظام:")
    
    courses = Course.objects.all()
    
    if not courses.exists():
        print("   ⚠ لا توجد دورات في النظام")
        return
    
    for course in courses:
        print(f"   • {course.name_ar or course.name} (ID: {course.id})")
    
    print(f"   📊 إجمالي الدورات: {courses.count()}")

def show_teacher_branches():
    """عرض فروع المدرسين"""
    from employ.models import Teacher
    
    print("\n👨‍🏫 فروع المدرسين:")
    
    teachers = Teacher.objects.all()
    
    for teacher in teachers:
        branches = teacher.branches or []
        if branches:
            print(f"   • {teacher.full_name}: {branches}")

def generate_final_report():
    """تقرير نهائي مبسط"""
    from employ.models import Teacher
    from accounts.models import Course, CourseTeacherAssignment
    from attendance.models import TeacherAttendance
    
    print("\n" + "="*60)
    print("📊 التقرير النهائي")
    print("="*60)
    
    # المدرسين والفروع
    print(f"\n👨‍🏫 المدرسين والفروع:")
    teachers_with_branches = Teacher.objects.exclude(branches=[]).count()
    print(f"   • إجمالي المدرسين: {Teacher.objects.count()}")
    print(f"   • المدرسين مع فروع: {teachers_with_branches}")
    
    # عرض بعض الأمثلة
    sample_teachers = Teacher.objects.exclude(branches=[])[:5]
    for teacher in sample_teachers:
        branches = teacher.branches or []
        print(f"   • {teacher.full_name}: {branches}")
    
    if teachers_with_branches > 5:
        print(f"   • ... و {teachers_with_branches - 5} مدرس آخر")
    
    # الدورات
    print(f"\n📚 الدورات:")
    courses_count = Course.objects.count()
    print(f"   • إجمالي الدورات: {courses_count}")
    
    # التعيينات
    print(f"\n🎯 تعيينات المدرسين:")
    assignments_count = CourseTeacherAssignment.objects.count()
    print(f"   • إجمالي التعيينات: {assignments_count}")
    
    # عرض بعض الأمثلة
    sample_assignments = CourseTeacherAssignment.objects.select_related('teacher', 'course')[:5]
    for assignment in sample_assignments:
        print(f"   • {assignment.teacher.full_name} → {assignment.course.name_ar or assignment.course.name}")
    
    if assignments_count > 5:
        print(f"   • ... و {assignments_count - 5} تعيين آخر")
    
    # حضور المدرسين
    print(f"\n📊 حضور المدرسين:")
    teacher_attendances_count = TeacherAttendance.objects.count()
    print(f"   • إجمالي سجلات الحضور: {teacher_attendances_count}")
    
    # إحصائيات الحضور
    present_count = TeacherAttendance.objects.filter(status='present').count()
    no_duty_count = TeacherAttendance.objects.filter(status='no_duty').count()
    print(f"   • الحضور: {present_count}, بدون دوام: {no_duty_count}")

def main():
    print("🚀 بدء إصلاح الفروع وربط الحضور")
    print("="*50)
    
    try:
        # 1. عرض الدورات الموجودة
        print("\n1. 📚 عرض الدورات الموجودة...")
        show_existing_courses()
        
        # 2. عرض فروع المدرسين
        print("\n2. 👨‍🏫 عرض فروع المدرسين...")
        show_teacher_branches()
        
        # 3. الإصلاح الكامل للفروع
        print("\n3. 🔧 الإصلاح الكامل لبيانات الفروع...")
        fixed_count = fix_teacher_branches_completely()
        
        # 4. تعيين المدرسين للدورات الموجودة
        print("\n4. 🎯 تعيين المدرسين للدورات الموجودة...")
        assignments_count = assign_teachers_to_existing_courses()
        
        # 5. ربط حضور المدرسين مع الدورات
        print("\n5. 📊 ربط حضور المدرسين مع الدورات...")
        linked_attendance_count = link_teacher_attendance_to_courses()
        
        # 6. التقرير النهائي
        generate_final_report()
        
        print(f"\n🎉 تم الانتهاء بنجاح!")
        print(f"   • تم إصلاح {fixed_count} مدرس")
        print(f"   • تم إنشاء {assignments_count} تعيين جديد")
        print(f"   • تم ربط {linked_attendance_count} سجل حضور مع دورات")
        
    except Exception as e:
        print(f"❌ خطأ: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()