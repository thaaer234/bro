# quick_restore.py
import os
import django
import sys
import json
from django.core import serializers

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from employ.models import Teacher
from accounts.models import CourseTeacherAssignment, Course, CostCenter

def quick_restore_latest():
    """استعادة أحدث نسخة احتياطية تلقائياً"""
    backup_dir = "complete_backups"
    
    if not os.path.exists(backup_dir):
        print("❌ مجلد النسخ الاحتياطية غير موجود!")
        return False
    
    # البحث عن أحدث ملف
    backup_files = []
    for file in os.listdir(backup_dir):
        if file.startswith('complete_backup_') and file.endswith('.json'):
            file_path = os.path.join(backup_dir, file)
            file_time = os.path.getctime(file_path)
            backup_files.append((file, file_time))
    
    if not backup_files:
        print("❌ لا توجد نسخ احتياطية متاحة!")
        return False
    
    # أحدث ملف
    latest_file = max(backup_files, key=lambda x: x[1])[0]
    latest_path = os.path.join(backup_dir, latest_file)
    
    print(f"🔄 استعادة أحدث نسخة احتياطية: {latest_file}")
    
    try:
        with open(latest_path, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        
        # استعادة البيانات
        if 'teachers' in backup_data['data'] and backup_data['data']['teachers']:
            Teacher.objects.all().delete()
            for obj in serializers.deserialize("json", backup_data['data']['teachers']):
                obj.save()
            print(f"✅ تم استعادة {Teacher.objects.count()} مدرس")
        
        if 'assignments' in backup_data['data'] and backup_data['data']['assignments']:
            CourseTeacherAssignment.objects.all().delete()
            for obj in serializers.deserialize("json", backup_data['data']['assignments']):
                obj.save()
            print(f"✅ تم استعادة {CourseTeacherAssignment.objects.count()} تعيين")
        
        if 'courses' in backup_data['data'] and backup_data['data']['courses']:
            Course.objects.all().delete()
            for obj in serializers.deserialize("json", backup_data['data']['courses']):
                obj.save()
            print(f"✅ تم استعادة {Course.objects.count()} دورة")
        
        if 'cost_centers' in backup_data['data'] and backup_data['data']['cost_centers']:
            CostCenter.objects.all().delete()
            for obj in serializers.deserialize("json", backup_data['data']['cost_centers']):
                obj.save()
            print(f"✅ تم استعادة {CostCenter.objects.count()} مركز كلفة")
        
        print("🎉 تم الاستعادة بنجاح!")
        return True
        
    except Exception as e:
        print(f"❌ خطأ في الاستعادة: {e}")
        return False

if __name__ == "__main__":
    quick_restore_latest()