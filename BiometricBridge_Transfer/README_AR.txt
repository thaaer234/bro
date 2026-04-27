طريقة نقل وتشغيل برنامج البصامة
================================

1. انسخ هذا المجلد كامل إلى اللابتوب الثاني.
   يفضل وضعه في مكان ثابت مثل:
   D:\BiometricBridge
   أو:
   C:\BiometricBridge

2. لا تنقل المجلد بعد التثبيت.
   إذا نقلته، شغل install_startup_task_as_admin.bat مرة ثانية من المكان الجديد.

3. للتجربة اليدوية:
   افتح:
   run_now.bat

4. للتشغيل الدائم:
   افتح:
   install_startup_task_as_admin.bat

   هذا لا يستخدم Task Scheduler ولا يحتاج صلاحيات Administrator.
   سيضيف ملف تشغيل واختصار داخل Startup folder الخاص بويندوز.
   وسيضيف Run registry entry للمستخدم الحالي كخطة احتياطية.
   عند تسجيل الدخول إلى ويندوز سيعمل watchdog مخفي.
   الـ watchdog يفحص كل دقيقة، وإذا برنامج البصامة واقف يشغله من جديد.

5. للتأكد:
   افتح:
   check_status.bat

   يجب أن ترى:
   - Startup entry exists
   - عملية biometric_bridge.exe شغالة
   - أو يظهر لوج جديد داخل biometric_bridge.log

6. لفحص اتصال البصامة والسيرفر:
   افتح:
   test_connection.bat

7. لإيقاف التشغيل الدائم:
   افتح:
   stop_and_remove_startup_task_as_admin.bat

ملاحظات مهمة
============

- لا تشغل البرنامج على جهازين بنفس الوقت حتى لا يتم إرسال البيانات مرتين.
- لازم اللابتوب يكون قادر يوصل للبصامة 172.16.0.2 وعلى الإنترنت بنفس الوقت.
- لا تحذف biometric_bridge_state.json لأنه يمنع تكرار إرسال السجلات القديمة.
- الإعداد الحالي يرسل كل 30 ثانية:
  "interval_seconds": 30
- إذا تغير IP البصامة، عدل:
  "device_ip"
  داخل biometric_bridge_config.json
