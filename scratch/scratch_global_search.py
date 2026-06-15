import os
import sys
import django

sys.path.append(r'c:\Users\THAAER\Desktop\project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

sys.stdout.reconfigure(encoding='utf-8')

from django.apps import apps
from django.db import models

search_terms = ["عبد الكريم", "عبدالكريم", "منجد", "عجاج"]

print("=== GLOBAL DATABASE SEARCH FOR SEARCH TERMS ===")
for app_config in apps.get_app_configs():
    for model in app_config.get_models():
        # Get all char/text fields
        text_fields = [f.name for f in model._meta.get_fields() if isinstance(f, (models.CharField, models.TextField))]
        if not text_fields:
            continue
        
        # Build query
        q_obj = models.Q()
        for field in text_fields:
            for term in search_terms:
                q_obj |= models.Q(**{f"{field}__icontains": term})
        
        try:
            results = model.objects.filter(q_obj)
            count = results.count()
            if count > 0:
                print(f"\nModel: {app_config.label}.{model.__name__} (Found {count} records):")
                # Print first 10 records
                for item in results[:10]:
                    print(f"  - [ID={item.pk}] {item}")
                    # Print values of fields containing search terms
                    for field in text_fields:
                        val = getattr(item, field, None)
                        if val and any(term in str(val) for term in search_terms):
                            print(f"    * {field}: {val}")
        except Exception as e:
            # Some models might fail due to database views or abstract/unmigrated tables
            pass
