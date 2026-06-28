# -*- coding: utf-8 -*-
import os
import sys
import builtins

# Setup path and environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
os.environ["DISABLE_BIOMETRIC_SCHEDULER"] = "true"

# Suppress debug prints from signals to speed it up and keep terminal clean
builtins.print = lambda *args, **kwargs: None

import django
django.setup()

# Restore original print to write directly to stdout
def custom_print(message):
    sys.__stdout__.write(str(message) + "\n")
    sys.__stdout__.flush()

from academic_years.models import AcademicYearTransferBatch
from academic_years.services.transfers import AcademicYearTransferService
from django.contrib.auth.models import User

def main():
    custom_print("🔄 البدء في ترحيل البيانات للفصل الدراسي الجديد...")
    try:
        batch = AcademicYearTransferBatch.objects.get(id=1)
        actor = User.objects.filter(is_superuser=True).first()
        
        custom_print(f"الفصل المصدر: {batch.source_academic_year}")
        custom_print(f"الفصل الهدف: {batch.target_academic_year}")
        custom_print("يرجى الانتظار، قد تستغرق العملية حوالي دقيقة بسبب حجم البيانات (350 تسجيل، 534 إيصال، 328 قيد مالي)...")
        
        service = AcademicYearTransferService(batch=batch, actor=actor)
        summary = service.execute()
        
        custom_print("\n🎉 اكتمل الترحيل بنجاح تام!")
        custom_print(f"الملخص: {dict(summary)}")
    except Exception as e:
        import traceback
        custom_print(f"\n❌ حدث خطأ أثناء الترحيل: {e}")
        # Restore sys.stderr
        traceback.print_exc(file=sys.__stderr__)

if __name__ == "__main__":
    main()
