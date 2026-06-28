import sys, os
import traceback
sys.stdout.reconfigure(encoding='utf-8')
# Setup django environment path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
os.environ["DISABLE_BIOMETRIC_SCHEDULER"] = "true"
import django
django.setup()

from django.db import transaction
from django.contrib.auth.models import User
from academic_years.models import AcademicYearTransferBatch
from academic_years.services.transfers import AcademicYearTransferService

def test():
    try:
        batch = AcademicYearTransferBatch.objects.get(id=1)
        actor = User.objects.filter(is_superuser=True).first()
        print(f"Loaded Batch 1: Source={batch.source_academic_year}, Target={batch.target_academic_year}")
        print(f"Actor: {actor.username}")
        
        # We will run the service execute method but we will NOT wrap it in a root view,
        # and we want to see the traceback of the actual database error.
        service = AcademicYearTransferService(batch=batch, actor=actor)
        
        # To prevent the log() method from raising TransactionManagementError when a DB error occurs,
        # we can temporarily override log to just print to console.
        original_log = service.log
        def safe_log(message, **kwargs):
            print(f"[Log] {message}")
            try:
                original_log(message, **kwargs)
            except Exception as le:
                print(f"[Log Failed to Write to DB] {le}")
        service.log = safe_log
        
        print("Executing transfer service...")
        service.execute()
        print("Completed successfully!")
    except Exception as e:
        print("\n❌ EXCEPTION CAUGHT:")
        print(type(e), str(e))
        traceback.print_exc()

if __name__ == "__main__":
    test()
