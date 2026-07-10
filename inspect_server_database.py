# -*- coding: utf-8 -*-
import os
import sys

def main():
    print("🔍 البحث عن ملفات قاعدة البيانات في السيرفر...")
    base_dir = "/var/www"
    
    found_any = False
    for root, dirs, files in os.walk(base_dir):
        # Skip virtualenvs or cache dirs to be fast
        if any(skip in root for skip in ['venv', '.git', '__pycache__', 'staticfiles', 'media']):
            continue
            
        for file in files:
            if file.endswith('.sqlite3'):
                found_any = True
                full_path = os.path.join(root, file)
                size_mb = os.path.getsize(full_path) / (1024 * 1024)
                print(f"\n📍 ملف قاعدة بيانات مكتشف: {full_path}")
                print(f"   الحجم: {size_mb:.2f} MB")
                
                # Try to count batches in this database
                try:
                    import sqlite3
                    conn = sqlite3.connect(full_path)
                    cursor = conn.cursor()
                    
                    # Check tables
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                    tables = [row[0] for row in cursor.fetchall()]
                    print(f"   عدد الجداول: {len(tables)}")
                    
                    if 'academic_years_academicyeartransferbatch' in tables:
                        cursor.execute("SELECT id FROM academic_years_academicyeartransferbatch;")
                        batch_ids = [row[0] for row in cursor.fetchall()]
                        print(f"   📋 معرفات دفعات الترحيل المتاحة: {batch_ids}")
                    else:
                        print("   ⚠️ لا يحتوي هذا الملف على جدول دفعات الترحيل.")
                        
                    if 'accounts_account' in tables:
                        cursor.execute("SELECT COUNT(*) FROM accounts_account;")
                        acc_count = cursor.fetchone()[0]
                        print(f"   👥 عدد الحسابات المالية: {acc_count}")
                    else:
                        print("   ⚠️ لا يحتوي هذا الملف على جدول الحسابات.")
                        
                    conn.close()
                except Exception as e:
                    print(f"   ❌ فشل في فحص الملف: {e}")
                    
    if not found_any:
        print("❌ لم يتم العثور على أي ملفات .sqlite3 في /var/www")

if __name__ == "__main__":
    main()
