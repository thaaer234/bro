from django.conf import settings
from django.apps import apps


def get_system_architecture_context():
    """
    Dynamically scans the Django project settings and active models 
    to provide the LLM with exact, comprehensive structural system context.
    """
    # 1. Database Configuration
    db_engine = settings.DATABASES.get('default', {}).get('ENGINE', '').split('.')[-1]
    
    # 2. Project Custom Apps
    project_apps = []
    for app in settings.INSTALLED_APPS:
        if not app.startswith('django.') and not app.startswith('rest_framework') and not app.startswith('corsheaders'):
            # clean up config class name if present
            app_name = app.split('.apps.')[0] if '.apps.' in app else app
            project_apps.append(app_name)
            
    # 3. Middleware
    middleware_list = [m.split('.')[-1] for m in settings.MIDDLEWARE]
    
    # 4. Models and Database Fields Schema
    models_schema = []
    # Apps we want to focus on (project custom apps)
    target_apps = [
        'students', 'employ', 'attendance', 'exams', 'courses', 
        'classroom', 'registration', 'announcements', 'accounts', 
        'academic_years', 'mobile', 'errors', 'quick', 'technical_services'
    ]
    
    try:
        for model in apps.get_models():
            app_label = model._meta.app_label
            if app_label in target_apps:
                model_name = model.__name__
                # Extract field names and types
                fields_info = []
                for field in model._meta.fields:
                    field_type = field.__class__.__name__
                    fields_info.append(f"{field.name} ({field_type})")
                
                models_schema.append(
                    f"   - تطبيق [{app_label}] -> نموذج [{model_name}]: الحقول هي: {', '.join(fields_info)}"
                )
    except Exception as e:
        models_schema.append(f"   (حدث خطأ أثناء فحص جداول قاعدة البيانات: {str(e)})")

    # Combine into formatted string
    apps_str = ", ".join(project_apps)
    middleware_str = ", ".join(middleware_list)
    models_str = "\n".join(models_schema[:65]) # Limit to 65 models to prevent prompt overflow
    
    context = f"""قاعدة البيانات المستخدمة: {db_engine}
- تطبيقات النظام المدمجة (INSTALLED_APPS): {apps_str}
- البرمجيات الوسيطة النشطة (MIDDLEWARE): {middleware_str}
- هيكلية جداول قاعدة البيانات والنماذج المسجلة (Database Schema & Models):
{models_str}"""
    return context.strip()


def generate_ai_prompt(report_instance):
    """
    Generates a structured prompt string that can be copy-pasted into an LLM
    to generate the technical solution fields for the report.
    """
    employee_name = report_instance.employee.get_full_name() or report_instance.employee.username
    issue = report_instance.issue_description
    job_title = report_instance.job_title
    department = report_instance.department
    
    # Retrieve the dynamically scanned system architecture context
    architecture_context = get_system_architecture_context()
    
    prompt = f"""
أنت مهندس برمجيات محترف وخبير في تطوير وتصحيح تطبيقات Django وقواعد البيانات ونظم تشغيل الويب.
لقد أبلغ الموظف: {employee_name} ({job_title} في قسم {department}) عن مشكلة تقنية حرجة في النظام.

تفاصيل المشكلة والشكوى المقدمة:
----------------------------------------
{issue}
----------------------------------------

معلومات هيكلية النظام المستهدف الدقيقة (System Architecture Context):
----------------------------------------
{architecture_context}
----------------------------------------

الرجاء تحليل هذه المشكلة بدقة وإنشاء البيانات الفنية اللازمة لملء تقرير الصيانة الفنية الرسمي.
بما أنك مطلع على هيكلية الجداول والنماذج في الأعلى، يرجى كتابة كود الحل البرمجي أو تعديلات قاعدة البيانات باستخدام أسماء الجداول والحقول الفعلية في النظام إذا كانت المشكلة ترتبط بها مباشرة (مثل التعامل مع الطلاب أو الموظفين أو الحسابات المالية).

يجب أن تكون إجابتك باللغة العربية الفصحى وبشكل رسمي ومنسق ومناسب للمستندات التنفيذية.

المخرجات المطلوبة هي:
1. تأثير المشكلة (Issue Impact): شرح دقيق لكيفية تأثير هذه المشكلة على استقرار النظام، الأداء العام، قاعدة البيانات، وسير العمليات الخاصة بالموظفين أو المستخدمين.
2. الحل البرمجي المطبق (Code Solution): كتابة الحل التقني المطبق كوداً (Django models/views, SQL updates, config files, dynamic scripts, etc.) أو تعليمات تعديل الأكواد البرمجية خطوة بخطوة مع توضيح سبب تطبيق هذا التعديل.
3. ما يجب على الموظف القيام به (Employee Instructions): كتابة خطوات إجرائية واضحة ومبسطة باللغة العربية يستطيع الموظف اتباعها لتجنب الوقوع في هذه المشكلة مجدداً أو كيفية التعامل معها في حال حدوثها بشكل مؤقت.
4. توصيات وملاحظات (Recommendations): كتابة اقتراحات لتحسينات مستقبلية على هيكلية البرمجيات، أو خادم الويب، أو إعدادات قاعدة البيانات لضمان عدم تكرار المشكلة نهائياً.

لإتمام المعالجة التلقائية، يرجى تقديم الإجابة في صيغة كائن JSON صالح فقط (Valid JSON Object) يحتوي على المفاتيح التالية:
{{
  "issue_impact": "كتابة تأثير المشكلة هنا...",
  "code_solution": "كتابة الحل البرمجي والتعديلات التقنية هنا...",
  "employee_instructions": "كتابة تعليمات الموظف هنا...",
  "recommendations": "كتابة التوصيات والملاحظات الفنية هنا..."
}}
"""
    return prompt.strip()
