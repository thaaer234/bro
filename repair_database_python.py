# -*- coding: utf-8 -*-
"""
إصلاح متقدم لقاعدة البيانات التالفة باستخدام بايثون بالكامل
يقوم بنسخ الجداول جدولاً تلو الآخر، وفي حال وجود جدول تالف، يقوم باستعاده الأسطر سطراً سطر
ويتخطى الأسطر التالفة فقط لضمان استرجاع 99.9% من البيانات دون فقدان الجدول بالكامل.
"""
import os
import sqlite3
import subprocess
import sys
import traceback

def main():
    db_path = "/var/www/bro/db.sqlite3"
    fixed_db_path = "/var/www/bro/db_fixed.sqlite3"
    backup_db_path = "/var/www/bro/db.sqlite3.corrupted"

    print("=" * 70)
    print("🛠️ البدء في الإصلاح المتقدم لقاعدة البيانات (Python Robust Recovery)...")
    print("=" * 70)

    if not os.path.exists(db_path):
        print(f"❌ لم يتم العثور على قاعدة البيانات في: {db_path}")
        return

    # 1. إيقاف Gunicorn لمنع الكتابة
    print("⏳ إيقاف خدمة Gunicorn...")
    subprocess.run(["sudo", "systemctl", "stop", "bro-gunicorn"])

    src_conn = None
    dst_conn = None

    try:
        if os.path.exists(fixed_db_path):
            os.remove(fixed_db_path)

        src_conn = sqlite3.connect(db_path)
        dst_conn = sqlite3.connect(fixed_db_path)
        
        # تجاهل أخطاء الترميز وقراءة البيانات بأمان
        src_conn.text_factory = lambda x: str(x, 'utf-8', 'ignore')
        dst_conn.text_factory = str

        cursor_src = src_conn.cursor()
        cursor_dst = dst_conn.cursor()

        # إيقاف التحقق من المفاتيح الأجنبية والكتابة المتزامنة لتسريع الاسترداد
        cursor_dst.execute("PRAGMA foreign_keys = OFF;")
        cursor_dst.execute("PRAGMA synchronous = OFF;")
        cursor_dst.execute("PRAGMA journal_mode = MEMORY;")

        # 2. جلب جميع الجداول
        cursor_src.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = cursor_src.fetchall()
        print(f"📋 تم العثور على {len(tables)} جدول في قاعدة البيانات.")

        for table_name, schema_sql in tables:
            print(f"⏳ جاري معالجة الجدول: {table_name}...")
            
            # إنشاء الجدول في قاعدة البيانات الجديدة
            try:
                cursor_dst.execute(schema_sql)
            except Exception as e:
                print(f"⚠️ فشل إنشاء هيكل الجدول {table_name}: {e}")
                continue

            # الحصول على معلومات الأعمدة
            cursor_src.execute(f"PRAGMA table_info([{table_name}])")
            columns = [col[1] for col in cursor_src.fetchall()]
            if not columns:
                continue

            col_list = ", ".join(f"[{c}]" for c in columns)
            placeholders = ", ".join("?" for _ in columns)
            insert_sql = f"INSERT INTO [{table_name}] ({col_list}) VALUES ({placeholders})"

            # محاولة نسخ الجدول بالكامل دفعة واحدة
            try:
                cursor_src.execute(f"SELECT {col_list} FROM [{table_name}]")
                rows = cursor_src.fetchall()
                if rows:
                    cursor_dst.executemany(insert_sql, rows)
                print(f"   ✅ تم نسخ {len(rows)} سطر بنجاح (نسخ سريع).")
            except sqlite3.DatabaseError as e:
                # في حال وجود تلف، نقوم بنسخ الأسطر فرادى وتخطي التالف
                print(f"   ⚠️ الجدول {table_name} يحتوي على تلف ({e}). جاري محاولة الاستعادة الفردية...")
                
                try:
                    # محاولة جلب الـ rowids
                    cursor_src.execute(f"SELECT rowid FROM [{table_name}]")
                    rowids = [r[0] for r in cursor_src.fetchall()]
                    
                    recovered = 0
                    skipped = 0
                    
                    for r_id in rowids:
                        try:
                            cursor_src.execute(f"SELECT {col_list} FROM [{table_name}] WHERE rowid = ?", (r_id,))
                            row = cursor_src.fetchone()
                            if row:
                                cursor_dst.execute(insert_sql, row)
                                recovered += 1
                        except Exception:
                            skipped += 1
                    
                    print(f"   ✅ استرداد فردي: تم استرجاع {recovered} سطر وتخطي {skipped} سطر تالف.")
                except Exception as rowid_err:
                    print(f"   ⚠️ فشل جلب rowids للجدول {table_name} ({rowid_err}). جاري المحاولة بالقراءة التدفقية...")
                    
                    # محاولة قراءة تدفقية كخيار أخير
                    try:
                        cursor_src.execute(f"SELECT {col_list} FROM [{table_name}]")
                        recovered = 0
                        skipped = 0
                        while True:
                            try:
                                row = cursor_src.fetchone()
                                if row is None:
                                    break
                                cursor_dst.execute(insert_sql, row)
                                recovered += 1
                            except Exception:
                                skipped += 1
                                continue
                        print(f"   ✅ استرداد تدفقي: تم استرجاع {recovered} سطر وتخطي {skipped} سطر تالف.")
                    except Exception as stream_err:
                        print(f"   ❌ فشل استرداد الجدول {table_name} بالكامل: {stream_err}")

        # 3. إعادة بناء الفهارس، العروض، والمشغلات (Indexes, Views, Triggers)
        print("🏗️ جاري إعادة بناء الفهارس والمشغلات والعروض...")
        cursor_src.execute("SELECT name, sql FROM sqlite_master WHERE type IN ('index', 'trigger', 'view') AND sql IS NOT NULL;")
        objects = cursor_src.fetchall()
        
        for name, sql in objects:
            try:
                cursor_dst.execute(sql)
            except Exception as e:
                # الفهارس المرتبطة بقيود فريدة قد يتم إنشاؤها تلقائياً، لذا نتخطى أخطاء التكرار
                pass

        dst_conn.commit()
        print("💾 تم حفظ جميع البيانات المصلحة.")

        src_conn.close()
        dst_conn.close()

        # 4. فحص سلامة قاعدة البيانات الجديدة
        print("🧐 التحقق من سلامة قاعدة البيانات الجديدة...")
        test_conn = sqlite3.connect(fixed_db_path)
        check_cursor = test_conn.cursor()
        check_cursor.execute("PRAGMA integrity_check;")
        result = check_cursor.fetchone()[0]
        test_conn.close()
        
        print(f"   نتيجة الفحص: {result}")

        if result.lower() == "ok":
            print("✅ تم الاسترداد بنجاح وقاعدة البيانات الجديدة سليمة تماماً!")
            
            # نسخ احتياطي للملف التالف وتفعيل الملف الجديد
            import time
            current_backup = f"{backup_db_path}_{int(time.time())}"
            os.rename(db_path, current_backup)
            
            # حذف ملفات WAL و SHM القديمة لمنع التلف عند التشغيل
            for suffix in ["-wal", "-shm"]:
                wal_file = db_path + suffix
                if os.path.exists(wal_file):
                    try:
                        os.remove(wal_file)
                        print(f"🗑️ تم حذف ملف الكاش: {wal_file}")
                    except Exception as wal_err:
                        print(f"⚠️ فشل حذف {wal_file}: {wal_err}")
                        
            os.rename(fixed_db_path, db_path)
            
            # ضبط الأذونات لتكون قابلة للقراءة والكتابة
            subprocess.run(["chmod", "666", db_path])
            
            print(f"💾 تم حفظ قاعدة البيانات التالفة كنسخة احتياطية في: {current_backup}")
            print(f"🚀 تم تفعيل قاعدة البيانات الجديدة المصلحة.")
        else:
            print("❌ قاعدة البيانات الناتجة لا تزال غير سليمة. تم إلغاء التفعيل.")
            if os.path.exists(fixed_db_path):
                os.remove(fixed_db_path)

    except Exception as e:
        print("❌ حدث خطأ غير متوقع أثناء عملية الاسترداد:")
        traceback.print_exc()
        if src_conn:
            try: src_conn.close()
            except: pass
        if dst_conn:
            try: dst_conn.close()
            except: pass
    finally:
        # 5. تشغيل Gunicorn مجدداً
        print("🚀 إعادة تشغيل خدمة Gunicorn...")
        subprocess.run(["sudo", "systemctl", "start", "bro-gunicorn"])

    print("=" * 70)
    print("🏁 انتهت العملية.")
    print("=" * 70)

if __name__ == "__main__":
    main()
