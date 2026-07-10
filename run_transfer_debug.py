# -*- coding: utf-8 -*-
"""
سكريبت لتشغيل الترحيل بشكل مباشر ومراقبة الخطأ التفصيلي
"""
import os, sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
os.environ["DISABLE_BIOMETRIC_SCHEDULER"] = "true"
import django
django.setup()

from academic_years.models import AcademicYearTransferBatch
from academic_years.services.transfers import AcademicYearTransferService
from django.contrib.auth.models import User
import traceback

def main():
    # جلب الدفعة رقم 1 أو أحدث دفعة مسودة/فاشلة
    batch = AcademicYearTransferBatch.objects.filter(id=1).first()
    if not batch:
        batch = AcademicYearTransferBatch.objects.all().first()
        
    if not batch:
        print("❌ لم يتم العثور على أي دفعة ترحيل!")
        return

    print(f"🔄 البدء في تشغيل الدفعة رقم {batch.id} بالوضع التفصيلي (Debug Mode)...")
    print(f"   الحالة الحالية: {batch.status}")
    print(f"   المصدر: {batch.source_academic_year}")
    print(f"   الهدف: {batch.target_academic_year}")
    
    # تعيين المستخدم الأول كمنفذ للعملية
    actor = User.objects.filter(is_superuser=True).first()
    if not actor:
        actor = User.objects.first()

    # محاولة تشغيل الترحيل
    try:
        service = AcademicYearTransferService(batch=batch, actor=actor)
        print("🚀 جاري البدء في execute()...")
        service.execute()
        print("✅ اكتمل الترحيل بنجاح!")
    except Exception as e:
        print("\n❌ ❌ ❌ حدث خطأ أثناء تنفيذ الترحيل:")
        print("=" * 80)
        traceback.print_exc()
        print("=" * 80)

if __name__ == "__main__":
    main()
