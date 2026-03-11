# fix_teacher_attendance_final.py
import os
import sys
import json
import django
from datetime import datetime, date
from decimal import Decimal

# إعداد إعدادات Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from django.utils import timezone
from django.db import transaction
from employ.models import Teacher
from attendance.models import TeacherAttendance

def load_schedule_from_json(file_path):
    """تحميل جدول الحضور من ملف JSON"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        print(f"❌ خطأ في تحميل الملف: {e}")
        return None

def create_teacher_name_mapping():
    """إنشاء خريطة مطابقة بين الأسماء الجزئية والأسماء الكاملة"""
    
    # خريطة المطابقة اليدوية الثابتة
    manual_mapping = {
        'إسراء': 'إسراء عودة(التمهيدي)',
        'رياض': 'رياض دالاتي (تمهيدي)',
        'عمار': 'عمار مرزوق (أدبي)',
        'يع': 'ربيع نجار',
        'خير السعدي': 'محمد السعدي',
        'علي بدوي': 'علي محفوض',
        # يمكنك إضافة المزيد هنا إذا عرفت المطابقات
    }
    
    return manual_mapping

def find_teacher_smart(teacher_name, name_mapping):
    """بحث ذكي عن المدرس"""
    
    # 1. التحقق من الخريطة اليدوية أولاً
    if teacher_name in name_mapping:
        full_name = name_mapping[teacher_name]
        try:
            return Teacher.objects.get(full_name=full_name)
        except Teacher.DoesNotExist:
            print(f"❌ المدرس {full_name} غير موجود!")
    
    # 2. البحث المباشر باستخدام الاسم الكامل
    teachers = Teacher.objects.filter(full_name__icontains=teacher_name)
    if teachers.count() == 1:
        return teachers.first()
    
    # 3. البحث باستخدام أجزاء الاسم
    name_parts = [part for part in teacher_name.split() if len(part) > 2]
    
    for part in name_parts:
        teachers = Teacher.objects.filter(full_name__icontains=part)
        if teachers.count() == 1:
            print(f"   🔍 تمت مطابقة '{teacher_name}' مع '{teachers.first().full_name}'")
            return teachers.first()
    
    # 4. إذا لم يتم العثور على مطابقة
    return None

def show_quick_stats(schedule_data):
    """عرض إحصائيات سريعة عن الجدول"""
    schedule = schedule_data.get('schedule', {})
    total_days = len(schedule)
    total_sessions = 0
    unique_teachers = set()
    
    for date_str, day_data in schedule.items():
        teachers_data = day_data.get('teachers', {})
        unique_teachers.update(teachers_data.keys())
        total_sessions += sum(teachers_data.values())
    
    print(f"📊 إحصائيات الجدول:")
    print(f"   📅 عدد الأيام: {total_days}")
    print(f"   👥 عدد المدرسين في الجدول: {len(unique_teachers)}")
    print(f"   📚 إجمالي الجلسات: {total_sessions}")
    print(f"   👨‍🏫 عدد المدرسين في النظام: {Teacher.objects.count()}")

@transaction.atomic
def create_attendance_for_matched_teachers(schedule_data, name_mapping):
    """إنشاء الحضور فقط للمدرسين المطابقين"""
    created_count = 0
    error_count = 0
    skipped_teachers = set()
    
    schedule = schedule_data.get('schedule', {})
    institute = schedule_data.get('institute', 'اليمان')
    
    print(f"\n🚀 بدء تسجيل الحضور للمدرسين المطابقين...")
    
    for date_str, day_data in schedule.items():
        try:
            # تحويل التاريخ
            attendance_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # تخطي التواريخ المستقبلية
            if attendance_date > timezone.now().date():
                continue
            
            teachers_data = day_data.get('teachers', {})
            day_name = day_data.get('day_name', '')
            
            day_created = 0
            day_skipped = 0
            
            for teacher_name, session_count in teachers_data.items():
                # البحث عن المدرس
                teacher = find_teacher_smart(teacher_name, name_mapping)
                
                if not teacher:
                    skipped_teachers.add(teacher_name)
                    day_skipped += 1
                    continue
                
                # التحقق من عدم وجود سجل مسبق
                existing = TeacherAttendance.objects.filter(
                    teacher=teacher,
                    date=attendance_date
                ).first()
                
                if existing:
                    continue
                
                try:
                    # إنشاء سجل الحضور
                    attendance = TeacherAttendance.objects.create(
                        teacher=teacher,
                        date=attendance_date,
                        status='present',
                        session_count=session_count,
                        half_session_count=0,
                        notes=f"تسجيل تلقائي - {institute}"
                    )
                    
                    # معالجة القيود المحاسبية
                    attendance._process_salary_accrual_after_save()
                    
                    day_created += 1
                    created_count += 1
                    
                except Exception as e:
                    error_count += 1
                    print(f"   ❌ خطأ في {teacher.full_name}: {e}")
            
            if day_created > 0:
                print(f"   ✅ {date_str}: تم تسجيل {day_created} مدرس")
        
        except Exception as e:
            print(f"❌ خطأ في تاريخ {date_str}: {e}")
            error_count += 1
    
    # عرض النتائج
    print(f"\n📋 النتائج النهائية:")
    print(f"   ✅ سجلات تم إنشاؤها: {created_count}")
    print(f"   ❌ أخطاء: {error_count}")
    print(f"   ⏩ تم تخطي: {len(skipped_teachers)} مدرس")
    
    if skipped_teachers:
        print(f"\n📝 المدرسين الذين تم تخطيهم:")
        for teacher in sorted(skipped_teachers):
            print(f"   ⏩ {teacher}")
    
    return created_count, error_count

def main():
    """الدالة الرئيسية المبسطة"""
    json_file_path = "teacher_schedule.json"
    
    if not os.path.exists(json_file_path):
        print(f"❌ ملف {json_file_path} غير موجود")
        return
    
    # تحميل البيانات
    print("📂 جاري تحميل جدول الحضور...")
    schedule_data = load_schedule_from_json(json_file_path)
    if not schedule_data:
        return
    
    # عرض المعلومات الأساسية
    start_date = schedule_data.get('start_date')
    end_date = schedule_data.get('end_date')
    institute = schedule_data.get('institute')
    
    print(f"🏫 المعهد: {institute}")
    print(f"📅 الفترة: من {start_date} إلى {end_date}")
    
    # عرض إحصائيات سريعة
    show_quick_stats(schedule_data)
    
    # إنشاء خريطة المطابقة
    name_mapping = create_teacher_name_mapping()
    
    print(f"\n🗺️ خريطة المطابقة الجاهزة:")
    for partial, full in name_mapping.items():
        print(f"   {partial} -> {full}")
    
    # تأكيد سريع
    response = input("\nهل تريد المتابعة بتسجيل الحضور للمدرسين المطابقين فقط؟ (y/n): ")
    if response.lower() != 'y':
        print("❌ تم إلغاء العملية")
        return
    
    # بدء التسجيل
    created_count, error_count = create_attendance_for_matched_teachers(schedule_data, name_mapping)
    
    print(f"\n🎉 تم الانتهاء!")
    if created_count > 0:
        print(f"💡 تم إنشاء {created_count} سجل حضور مع قيود الرواتب التلقائية")

if __name__ == "__main__":
    main()