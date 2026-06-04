# -*- coding: utf-8 -*-
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
import django
django.setup()

from accounts.models import Account
acc = Account.objects.get(id=2724)
print(f"Current Balance for Account 2724: {acc.balance}")
