from pathlib import Path
import re

from django.templatetags.static import static


MANUAL_CHAPTERS = [
    {
        "slug": "login",
        "title": "تسجيل الدخول وبداية الجلسة",
        "icon": "fa-right-to-bracket",
        "summary": "هذا الفصل يشرح الدخول الصحيح إلى النظام، قراءة شاشة الدخول، وكيف تبدأ جلستك بدون أخطاء.",
        "shots": [
            {
                "title": "شاشة تسجيل الدخول",
                "path": static("img/manual-center/login-screen.png"),
                "caption": "واجهة الدخول الرسمية التي تحتوي اسم المستخدم، كلمة المرور، وزر طلب إعادة التعيين.",
            },
            {
                "title": "بوابة النظام بعد الدخول",
                "path": static("img/manual-center/welcome-screen.png"),
                "caption": "أول شاشة تشغيلية بعد نجاح الدخول، ومنها تنتقل إلى باقي الأقسام.",
            },
        ],
        "steps": [
            "افتح رابط النظام الداخلي ثم انتظر ظهور صفحة تسجيل الدخول بالكامل.",
            "أدخل اسم المستخدم في الحقل الأول كما هو معتمد لك داخل النظام.",
            "أدخل كلمة المرور في الحقل الثاني، ويمكنك استخدام زر إظهار كلمة المرور للتحقق منها قبل الإرسال.",
            "اضغط زر `تسجيل الدخول` ليبدأ التحقق والدخول إلى الجلسة.",
            "إذا كانت كلمة المرور منسية استخدم زر `طلب إعادة تعيين كلمة المرور` بدل المحاولات العشوائية.",
            "بعد الدخول الناجح انتقل أولاً إلى بوابة النظام أو لوحة التحكم بحسب طبيعة عملك.",
        ],
        "focus_pages": [
            {"label": "تسجيل الدخول", "path": "/login/", "purpose": "الدخول الآمن إلى النظام."},
            {"label": "طلب إعادة التعيين", "path": "/registration/password-reset-request/", "purpose": "بدء مسار استعادة كلمة المرور."},
            {"label": "الملف الشخصي", "path": "/registration/profile/", "purpose": "مراجعة بياناتك بعد الدخول."},
        ],
    },
    {
        "slug": "navigation",
        "title": "التنقل الذكي داخل النظام",
        "icon": "fa-compass",
        "summary": "يفسّر هذا الفصل كيف تتنقل بسرعة بين الأقسام باستخدام القائمة الجانبية، البطاقات، والاختصارات.",
        "shots": [
            {
                "title": "القائمة الجانبية الرئيسية",
                "path": static("img/manual-center/sidebar-screen.png"),
                "caption": "المدخل الموحد إلى المحاسبة، الطلاب، الحضور، الموارد البشرية، والتقارير.",
            },
            {
                "title": "لوحة التحكم العامة",
                "path": static("img/manual-center/dashboard-screen.png"),
                "caption": "شاشة ملخص تساعدك على فهم النشاط الجاري قبل الانتقال إلى التفاصيل.",
            },
        ],
        "steps": [
            "ابدأ دائمًا من القائمة الجانبية اليمنى لأنها تحتوي كل الأقسام الرئيسية.",
            "إذا رأيت سهمًا بجانب اسم القسم فهذا يعني أن القسم يحتوي صفحات فرعية؛ اضغطه لتوسيع القائمة.",
            "راقب تمييز العنصر النشط في القائمة حتى تعرف موقعك الحالي داخل النظام.",
            "استخدم الشريط العلوي لمعرفة التاريخ، اسم المستخدم الحالي، وبعض الاختصارات الجاهزة.",
            "إذا كنت على الجوال استخدم زر القائمة الدائري أعلى اليمين لفتح وإغلاق الشريط الجانبي.",
            "للانتقال السريع استخدم الاختصارات مثل `Ctrl + \`` للمحاسبة أو الاختصارات المعروضة في الواجهة.",
        ],
        "focus_pages": [
            {"label": "بوابة النظام", "path": "/pages/", "purpose": "شاشة ترحيب وتشغيل موحدة."},
            {"label": "لوحة التحكم", "path": "/pages/index", "purpose": "متابعة النشاط والإحصاءات."},
            {"label": "خريطة الموقع", "path": "/pages/sitemap/", "purpose": "مرجع سريع للمسارات العامة."},
            {"label": "دليل المستخدم", "path": "/pages/user-guide/", "purpose": "خريطة استعمال مبسطة للأقسام."},
        ],
    },
    {
        "slug": "students",
        "title": "الطلاب والتسجيل والاستقبال",
        "icon": "fa-user-graduate",
        "summary": "من إنشاء الطالب إلى ملفه الشخصي والتسجيل بالدورات والإيصالات السريعة.",
        "shots": [
            {
                "title": "قائمة الطلاب النظاميين",
                "path": static("img/manual-center/students-screen.png"),
                "caption": "شاشة المتابعة الأساسية للطلاب النظاميين مع البحث والتصفية والعمليات السريعة.",
            },
            {
                "title": "الطلاب السريعون",
                "path": static("img/manual-center/quick-students-screen.png"),
                "caption": "واجهة استقبال مرنة للتسجيلات السريعة وفتح الملفات وإصدار الإيصالات.",
            },
        ],
        "steps": [
            "افتح قسم `الطلاب` من القائمة الجانبية ثم اختر بين الطلاب النظاميين أو الطلاب السريعين.",
            "لإضافة طالب جديد ابدأ من `إضافة طالب` أو `إضافة طالب سريع` بحسب نوع المسار المطلوب.",
            "بعد الحفظ انتقل إلى ملف الطالب أو صفحة التسجيل في دورة لاستكمال العملية.",
            "من قائمة الطلاب استخدم البحث النصي والفلاتر للعثور على الطالب بالاسم أو الرقم أو الهاتف.",
            "من أزرار الصف يمكنك فتح الملف، كشف الحساب، التسجيل في دورة، أو تنفيذ الإيصال السريع.",
            "عند الحاجة إلى متابعة مالية أو انسحاب أو استرداد، افتح ملف الطالب أولاً ثم نفّذ الإجراء المناسب.",
        ],
        "focus_pages": [
            {"label": "الطلاب النظاميون", "path": "/students/", "purpose": "عرض الطلاب النظاميين وإدارة بياناتهم."},
            {"label": "إضافة طالب", "path": "/students/student-type-choice/", "purpose": "بدء تسجيل طالب جديد."},
            {"label": "بحث الطلاب", "path": "/students/search/", "purpose": "الوصول السريع إلى الطالب المطلوب."},
            {"label": "المجموعات الطلابية", "path": "/students/groups/", "purpose": "متابعة الطلاب بحسب المجموعات."},
            {"label": "الأرقام الطلابية", "path": "/students/numbers/", "purpose": "متابعة التسلسل والعدّ."},
            {"label": "الطلاب السريعون", "path": "/quick/students/", "purpose": "إدارة التسجيلات السريعة."},
            {"label": "إضافة طالب سريع", "path": "/quick/students/create/", "purpose": "تسجيل سريع مناسب للرسبشن."},
            {"label": "تسجيل في دورة سريعة", "path": "/quick/enrollments/create/", "purpose": "ربط الطالب بدورة ودفعته."},
        ],
    },
    {
        "slug": "education",
        "title": "الدورات والشعب والحضور والامتحانات",
        "icon": "fa-school",
        "summary": "الفصل التشغيلي للتوجيه: الدورات السريعة، الجلسات، الشعب، الحضور، الفرز، والتقارير التعليمية.",
        "shots": [
            {
                "title": "الدورات السريعة",
                "path": static("img/manual-center/quick-courses-screen.png"),
                "caption": "من هنا تُدار الدورات والجلسات والجداول والحضور الخاص بالمسار السريع.",
            },
            {
                "title": "إدارة الحضور",
                "path": static("img/manual-center/attendance-screen.png"),
                "caption": "مركز مراجعة السجلات اليومية، تحديث الحضور، والدخول إلى التفاصيل.",
            },
        ],
        "steps": [
            "ابدأ من `الدورات السريعة` إذا كان العمل متعلقًا بجلسات المسار السريع أو القاعات أو الجداول.",
            "من صفحة الدورة يمكنك الدخول إلى إدارة الجلسات، خيارات الوقت، التوليد التلقائي، أو نقل الطلاب.",
            "استخدم `الفرز اليدوي` و`تقاطع الطلاب` عندما تظهر تعارضات أو تحتاج إعادة توزيع دقيقة.",
            "للحضور اليومي افتح قسم `إدارة الحضور` ثم استخدم البحث حسب الشعبة أو التاريخ قبل فتح السجل المطلوب.",
            "لتسجيل حضور جديد استخدم `تسجيل الحضور` أو `حضور الدورات السريعة` بحسب نوع العملية.",
            "للمواد والنتائج افتح `العلامات` ثم ادخل إلى قائمة الامتحانات الخاصة بالشعبة واكمل الإدخال أو الطباعة.",
        ],
        "focus_pages": [
            {"label": "الدورات السريعة", "path": "/quick/courses/", "purpose": "إدارة الدورات والجلسات والقاعات."},
            {"label": "القاعات السريعة", "path": "/quick/classrooms/", "purpose": "متابعة القاعات والطاقة الاستيعابية."},
            {"label": "الفرز اليدوي", "path": "/quick/reports/manual-sorting/", "purpose": "إعادة توزيع الطلاب على الجلسات."},
            {"label": "تقاطع الطلاب", "path": "/quick/reports/student-intersections/", "purpose": "تحليل التعارضات بين التسجيلات."},
            {"label": "حضور الطلاب", "path": "/attendance/attendance/", "purpose": "سجل الحضور النظامي."},
            {"label": "حضور الدورات السريعة", "path": "/quick/attendance/quick-courses/", "purpose": "سجل الجلسات السريعة."},
            {"label": "الشعب الدراسية", "path": "/classroom/classroom/", "purpose": "إدارة الشعب والطلاب والمواد."},
            {"label": "لوحة الامتحانات", "path": "/exams/", "purpose": "إدارة الامتحانات والدرجات."},
        ],
    },
    {
        "slug": "accounting",
        "title": "المحاسبة والتحصيل والتقارير",
        "icon": "fa-file-invoice-dollar",
        "summary": "هذا الفصل مخصص للمحاسب المتمرس: القيود، السندات، الفترات، الميزانيات، الذمم، والتقارير المتقدمة.",
        "shots": [
            {
                "title": "لوحة المحاسبة",
                "path": static("img/manual-center/accounts-dashboard-screen.png"),
                "caption": "شاشة البداية للمحاسب وفيها مؤشرات الأداء والعمليات اليومية السريعة.",
            },
            {
                "title": "مركز التقارير المالية",
                "path": static("img/manual-center/accounts-reports-screen.png"),
                "caption": "بوابة التقارير التحليلية مثل ميزان المراجعة والميزانية وقائمة الدخل.",
            },
        ],
        "steps": [
            "افتح `المحاسبة` من القائمة الجانبية لتصل إلى لوحة التشغيل المالية.",
            "لإدخال حركة مالية جديدة انتقل إلى `قيد جديد` أو `إنشاء إيصال طالب` أو `إنشاء مصروف` بحسب الحالة.",
            "راجع `دليل الحسابات` قبل إنشاء حسابات أو عند الحاجة لفهم التبويب المالي الصحيح.",
            "إذا كانت العملية مرتبطة بزمن محاسبي افتح `الفترات المحاسبية` وتأكد أن الفترة مفتوحة.",
            "لمتابعة الذمم استخدم `المبالغ المستحقة` أو تقارير المسار السريع المتأخرة قبل اتخاذ إجراء التحصيل.",
            "في نهاية المتابعة استخدم `مركز التقارير` لاستخراج ميزان المراجعة أو قائمة الدخل أو الميزانية العمومية.",
        ],
        "focus_pages": [
            {"label": "لوحة المحاسبة", "path": "/accounts/", "purpose": "مدخل عام للمحاسب."},
            {"label": "دليل الحسابات", "path": "/accounts/chart/", "purpose": "إدارة شجرة الحسابات."},
            {"label": "القيود اليومية", "path": "/accounts/journal/", "purpose": "تسجيل ومراجعة وترحيل القيود."},
            {"label": "الإيصالات والمصاريف", "path": "/accounts/receipts-expenses/", "purpose": "مراجعة السندات اليومية."},
            {"label": "إنشاء إيصال طالب", "path": "/accounts/receipts/create/", "purpose": "تحصيل الرسوم وربطها بالحسابات."},
            {"label": "الفترات المحاسبية", "path": "/accounts/periods/", "purpose": "فتح وإغلاق الفترات."},
            {"label": "الميزانيات", "path": "/accounts/budgets/", "purpose": "إدارة الخطط المالية."},
            {"label": "مركز التقارير", "path": "/accounts/reports/", "purpose": "الوصول إلى التقارير المالية."},
        ],
    },
    {
        "slug": "admin",
        "title": "الموارد البشرية والإدارة والرقابة",
        "icon": "fa-user-shield",
        "summary": "يشرح إدارة الموظفين، المدرسين، الرواتب، الإجازات، التعاميم، الأمن، وصلاحيات المستخدمين.",
        "shots": [
            {
                "title": "الموارد البشرية",
                "path": static("img/manual-center/hr-screen.png"),
                "caption": "شاشة الموظفين التي تحتوي البحث، الفلاتر، والانتقال إلى الملف أو الصلاحيات.",
            },
        ],
        "steps": [
            "انتقل إلى `الموارد البشرية` لمتابعة الموظفين والبيانات الوظيفية والصلاحيات.",
            "من قائمة الموظفين استخدم البحث حسب الاسم أو المنصب ثم افتح الملف أو الصلاحيات أو التعديل.",
            "لإدارة الرواتب انتقل إلى `إدارة الرواتب` ثم راجع الاستحقاقات والخصومات والحالة النهائية.",
            "لإدارة الإجازات افتح `الإجازات` وأنشئ أو حدّث الطلب حسب حالة الموظف.",
            "المدرسون لهم مسار مستقل من `المدرسون` لمتابعة ملفاتهم وسلفهم ورواتبهم الخاصة.",
            "للرقابة العليا افتح `مركز الأمن` و`تقرير النظام` و`التعاميم` حسب نوع المتابعة الإدارية المطلوبة.",
        ],
        "focus_pages": [
            {"label": "الموارد البشرية", "path": "/employ/hr/", "purpose": "متابعة الموظفين والملفات الوظيفية."},
            {"label": "المدرسون", "path": "/employ/teachers/", "purpose": "إدارة ملفات المدرسين."},
            {"label": "إدارة الرواتب", "path": "/employ/salary-management/", "purpose": "مراجعة الرواتب والاستحقاقات."},
            {"label": "الإجازات", "path": "/employ/vacations/", "purpose": "إدارة طلبات الإجازة."},
            {"label": "مركز الأمن", "path": "/security/", "purpose": "رقابة أمنية وتشغيلية."},
            {"label": "تقرير النظام", "path": "/pages/system-report/", "purpose": "متابعة تشغيلية عليا للمشرف."},
            {"label": "التعاميم", "path": "/announcements/", "purpose": "إدارة الرسائل الداخلية."},
            {"label": "إدارة كلمات المرور", "path": "/registration/superuser-password-reset/", "purpose": "معالجة حالات إعادة تعيين كلمات المرور."},
        ],
    },
]


URL_INVENTORY_SOURCES = [
    ("registration/urls.py", "الحساب والدخول", "/registration/"),
    ("pages/urls.py", "الصفحات العامة والإدارة", "/pages/"),
    ("students/urls.py", "الطلاب النظاميون", "/students/"),
    ("quick/urls.py", "النظام السريع", "/quick/"),
    ("attendance/urls.py", "الحضور", "/attendance/"),
    ("classroom/urls.py", "الشعب الدراسية", "/classroom/"),
    ("exams/urls.py", "الامتحانات", "/exams/"),
    ("accounts/urls.py", "المحاسبة", "/accounts/"),
    ("employ/urls.py", "الموارد البشرية والمدرسون", "/employ/"),
    ("courses/urls.py", "المواد الدراسية", "/courses/"),
    ("errors/urls.py", "الرقابة والأخطاء", "/errors/"),
]


def _route_hint(name, path):
    hint_map = [
        ("create", "إنشاء عنصر جديد"),
        ("update", "تعديل عنصر موجود"),
        ("edit", "تحرير بيانات"),
        ("delete", "حذف أو إزالة"),
        ("detail", "عرض التفاصيل"),
        ("profile", "فتح الملف التفصيلي"),
        ("report", "تقرير أو ملحق تحليلي"),
        ("print", "طباعة أو إخراج ورقي"),
        ("export", "تصدير ملف"),
        ("attendance", "وظيفة حضور أو دوام"),
        ("statement", "كشف حساب أو بيان"),
        ("receipt", "إيصال أو سند"),
        ("salary", "رواتب أو استحقاقات"),
        ("advance", "سلفة مالية"),
        ("permission", "إدارة صلاحيات"),
        ("dashboard", "لوحة متابعة رئيسية"),
    ]
    combined = f"{name} {path}".lower()
    for key, text in hint_map:
        if key in combined:
            return text
    return "مسار تشغيلي داخل هذا التطبيق"


def build_route_inventory():
    pattern = re.compile(r"path\('([^']*)'.*name=['\"]([^'\"]+)['\"]")
    groups = []
    for relative_path, title, prefix in URL_INVENTORY_SOURCES:
        file_path = Path(relative_path)
        if not file_path.exists():
            continue
        entries = []
        text = file_path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            match = pattern.search(line)
            if not match:
                continue
            route_path, name = match.groups()
            full_path = prefix if not route_path else f"{prefix}{route_path}"
            entries.append(
                {
                    "name": name,
                    "path": full_path,
                    "hint": _route_hint(name, route_path),
                }
            )
        groups.append(
            {
                "title": title,
                "count": len(entries),
                "routes": entries,
            }
        )
    return groups


def build_manual_center_context():
    route_groups = build_route_inventory()
    route_total = sum(group["count"] for group in route_groups)
    return {
        "manual_chapters": MANUAL_CHAPTERS,
        "manual_route_groups": route_groups,
        "manual_chapter_count": len(MANUAL_CHAPTERS),
        "manual_route_total": route_total,
    }
