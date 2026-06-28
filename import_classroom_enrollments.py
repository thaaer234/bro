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

from quick.models import AcademicYear
from classroom.models import Classroom, Classroomenrollment
from students.models import Student

def normalize_name(name):
    if not name:
        return ""
    # إزالة المسافات الزائدة والبدء والانتهاء
    name = " ".join(name.strip().split())
    # توحيد الألف
    name = name.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    # توحيد الياء
    name = name.replace("ى", "ي")
    # توحيد التاء المربوطة والهاء
    name = name.replace("ة", "ه")
    return name

def clean_phone(p):
    if not p:
        return ""
    # إبقاء الأرقام فقط
    return "".join(c for c in str(p) if c.isdigit())

def main():
    print("=" * 80)
    print("📥 استيراد بيانات انضمام الطلاب للشعب في الفصل الجديد (نسخة مطابقة ذكية)")
    print("=" * 80)

    # 1. التحقق من الفصل الدراسي النشط
    target_year = AcademicYear.objects.filter(is_active=True).first()
    if not target_year:
        print("❌ خطأ: لا يوجد فصل دراسي نشط في النظام!")
        return
    print(f"✅ الفصل الدراسي النشط حالياً: {target_year.name} (ID: {target_year.id})")

    # 2. قراءة ملف JSON
    input_filename = "classroom_enrollments.json"
    if not os.path.exists(input_filename):
        print(f"❌ خطأ: لم يتم العثور على الملف '{input_filename}'!")
        print("تأكد من وجود الملف في نفس المجلد الذي تشغل منه السكربت.")
        return

    with open(input_filename, 'r', encoding='utf-8') as f:
        enrollments_data = json.load(f)

    print(f"✅ تم قراءة {len(enrollments_data)} تسجيل طالب من ملف JSON.")

    # 3. طلب تأكيد
    try:
        confirm = input("\n⚠️ هل تريد البدء بعملية ربط الطلاب بالشعب في الفصل الجديد؟ (اكتب 'نعم' للتأكيد): ")
    except KeyboardInterrupt:
        print("\n❌ تم إلغاء العملية.")
        return

    if confirm.strip() != "نعم":
        print("❌ تم إلغاء العملية ولم يتم تعديل أي بيانات.")
        return

    print("\n⏳ جاري تحميل طلاب الفصل الجديد وتحليل أسمائهم لتفادي أخطاء الإملاء...")
    
    # بناء قاعدة بيانات مؤقتة لمطابقة الطلاب بذكاء وسرعة
    target_students = Student.objects.filter(academic_year=target_year)
    print(f"📋 عدد الطلاب المتواجدين في الفصل الجديد: {target_students.count()}")
    
    students_by_name_phone = {}
    students_by_name_only = {}
    
    for s in target_students:
        norm_name = normalize_name(s.full_name)
        phone_cleaned = clean_phone(s.phone)
        
        # خريطة الاسم ورقم الهاتف
        if phone_cleaned:
            students_by_name_phone[(norm_name, phone_cleaned)] = s
            
        # خريطة الاسم فقط
        students_by_name_only[norm_name] = s

    print("\n⏳ جاري ربط الطلاب بالشعب...")
    
    enrolled_count = 0
    not_found_count = 0
    already_enrolled_count = 0

    for item in enrollments_data:
        full_name = item['full_name']
        phone = item['phone']
        classroom_id = item['classroom_id']
        classroom_name = item['classroom_name']

        # أ. البحث عن الشعبة
        classroom = Classroom.objects.filter(id=classroom_id).first()
        if not classroom:
            classroom = Classroom.objects.filter(name=classroom_name, is_visible=True).first()
        
        if not classroom:
            print(f"⚠️ الشعبة '{classroom_name}' (ID: {classroom_id}) غير موجودة. تخطي الطالب {full_name}.")
            continue

        # ب. البحث عن الطالب بذكاء ومطابقة الإملاء والمسافات
        norm_name = normalize_name(full_name)
        phone_cleaned = clean_phone(phone)
        
        student = None
        
        # 1. محاولة المطابقة بالاسم ورقم الهاتف معاً أولاً
        if phone_cleaned:
            student = students_by_name_phone.get((norm_name, phone_cleaned))
            
        # 2. محاولة المطابقة بالاسم فقط
        if not student:
            student = students_by_name_only.get(norm_name)

        if not student:
            print(f"❌ الطالب '{full_name}' (هاتف: {phone}) غير موجود في الفصل الجديد.")
            not_found_count += 1
            continue

        # ج. تسجيل الطالب في الشعبة
        env, created = Classroomenrollment.objects.get_or_create(
            classroom=classroom,
            student=student
        )
        if created:
            enrolled_count += 1
        else:
            already_enrolled_count += 1

    print("=" * 80)
    print("📊 ملخص عملية الاستيراد:")
    print(f" - إجمالي السجلات التي تمت معالجتها: {len(enrollments_data)}")
    print(f" - الطلاب الذين تم ربطهم بالشعب بنجاح: {enrolled_count}")
    print(f" - الطلاب المسجلين مسبقاً (تم تخطيهم): {already_enrolled_count}")
    print(f" - الطلاب الذين لم يتم العثور عليهم في الفصل الجديد: {not_found_count}")
    print("=" * 80)
    print("🎉 انتهت العملية بنجاح!")

if __name__ == '__main__':
    main()
