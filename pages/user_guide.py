from django.templatetags.static import static


USER_GUIDE_MODULES = [
    {
        "slug": "reception",
        "title": "الاستقبال والتسجيل",
        "icon": "fa-id-card-clip",
        "audience": "الرسبشن والاستقبال",
        "summary": "المسارات اليومية الخاصة باستقبال الطلاب، إنشاء السجلات، التسجيل السريع، البحث، وإصدار الإيصالات المباشرة.",
        "features": [
            {"name": "بوابة النظام", "path": "/pages/", "icon": "fa-compass", "purpose": "نقطة الدخول البصرية إلى النظام، ومنها يبدأ المستخدم فهم الواجهة والتنقل العام.", "actions": ["مراجعة الواجهة", "الانتقال إلى الأقسام", "الوصول للأدوات الأساسية"]},
            {"name": "إضافة طالب نظامي", "path": "/students/student-type-choice/", "icon": "fa-user-plus", "purpose": "فتح مسار تسجيل طالب جديد حسب نوعه قبل إدخاله في النظام.", "actions": ["اختيار نوع الطالب", "بدء التسجيل", "استكمال البيانات الأساسية"]},
            {"name": "قائمة الطلاب النظاميين", "path": "/students/student/", "icon": "fa-users", "purpose": "استعراض الطلاب المسجلين ومتابعة بياناتهم وفتح ملفاتهم الفردية.", "actions": ["بحث", "تصفية", "عرض ملف الطالب", "تحديث البيانات"]},
            {"name": "الطلاب السريعون", "path": "/quick/students/", "icon": "fa-bolt", "purpose": "إدارة تسجيلات المسار السريع ومتابعة بياناتهم ورسومهم بشكل أسرع.", "actions": ["عرض الطلاب", "فتح الملف", "تسجيل في دورة", "طباعة إيصال"]},
            {"name": "إضافة طالب سريع", "path": "/quick/students/create/", "icon": "fa-user-plus", "purpose": "تسجيل طالب في النظام السريع مع تدفق مختصر مناسب للاستقبال.", "actions": ["إدخال البيانات", "حفظ الطالب", "الانتقال للتسجيل بالدورة"]},
            {"name": "تسجيل سريع في دورة", "path": "/quick/enrollments/create/", "icon": "fa-clipboard-check", "purpose": "ربط الطالب بدورة سريعة مع التقاط بيانات الرسوم والخصم والحصص.", "actions": ["اختيار الطالب", "اختيار الدورة", "تثبيت التسجيل", "اعتماد الدفعة"]},
            {"name": "إنشاء إيصال طالب", "path": "/accounts/receipts/create/", "icon": "fa-receipt", "purpose": "إصدار إيصال رسمي للرسوم أو الأقساط وربطه بالحسابات.", "actions": ["تحديد الطالب", "تحديد المبلغ", "اعتماد السند", "طباعة الإيصال"]},
            {"name": "ملف المستخدم الشخصي", "path": "/registration/profile/", "icon": "fa-id-badge", "purpose": "مراجعة بيانات المستخدم وتحديث الصورة الشخصية ومعلومات الحساب.", "actions": ["عرض الملف", "تحديث البيانات", "تعديل الصورة"]},
        ],
    },
    {
        "slug": "guidance",
        "title": "التوجيه والمتابعة التعليمية",
        "icon": "fa-school",
        "audience": "التوجيه والمتابعة",
        "summary": "إدارة الشعب، الدورات السريعة، الحضور، التقاطعات، الفرز، والعلامات الدراسية.",
        "features": [
            {"name": "الشعب الدراسية", "path": "/classroom/classroom/", "icon": "fa-chalkboard", "purpose": "إدارة الشعب وربط الطلاب بها ومتابعة الطلاب والمواد داخل كل شعبة.", "actions": ["عرض الشعب", "إنشاء شعبة", "تعيين طلاب", "استعراض مواد الشعبة"]},
            {"name": "الدورات السريعة", "path": "/quick/courses/", "icon": "fa-layer-group", "purpose": "مركز إدارة الدورات السريعة، الجداول، القاعات، والمواعيد.", "actions": ["عرض الدورات", "إنشاء دورة", "إدارة الجلسات", "إعداد الجداول"]},
            {"name": "القاعات السريعة", "path": "/quick/classrooms/", "icon": "fa-door-open", "purpose": "تنظيم قاعات المسار السريع وربطها بالجلسات والطاقة الاستيعابية.", "actions": ["عرض القاعات", "إضافة قاعة", "تعديل القاعة"]},
            {"name": "حضور الطلاب", "path": "/attendance/attendance/", "icon": "fa-calendar-check", "purpose": "متابعة حضور الطلاب وإدارة السجلات اليومية والعمليات المرتبطة بها.", "actions": ["عرض السجل", "تسجيل حضور", "فتح التفاصيل"]},
            {"name": "حضور الدورات السريعة", "path": "/quick/attendance/quick-courses/", "icon": "fa-stopwatch", "purpose": "لوحة مخصصة لمتابعة حضور الجلسات السريعة وأرشيفها.", "actions": ["فتح جلسة", "تسجيل حضور", "عرض الأرشيف"]},
            {"name": "تقاطع الطلاب", "path": "/quick/reports/student-intersections/", "icon": "fa-shuffle", "purpose": "كشف تعارضات وتقاطعات الطلاب بين الدورات والمواعيد والقاعات.", "actions": ["تحليل التعارض", "مراجعة النتائج", "اتخاذ قرار النقل أو التعديل"]},
            {"name": "الفرز اليدوي", "path": "/quick/reports/manual-sorting/", "icon": "fa-sort", "purpose": "توزيع الطلاب على جلسات المسار السريع بشكل شبه يدوي مع حفظ جماعي.", "actions": ["اختيار المرحلة", "إعادة توزيع", "حفظ جماعي", "طباعة"]},
            {"name": "العلامات والامتحانات", "path": "/exams/dashboard/", "icon": "fa-square-poll-vertical", "purpose": "إدارة الامتحانات والدرجات واستعراض النتائج والطباعة.", "actions": ["لوحة العلامات", "إنشاء امتحان", "إدخال درجات", "طباعة النتائج"]},
        ],
    },
    {
        "slug": "accounting",
        "title": "المحاسبة والتحصيل",
        "icon": "fa-file-invoice-dollar",
        "audience": "المحاسبة",
        "summary": "مركز شامل للقيود، الأدلة، الميزانيات، السندات، السلف، والتقارير المالية المتقدمة.",
        "features": [
            {"name": "لوحة المحاسبة", "path": "/accounts/", "icon": "fa-chart-line", "purpose": "المدخل الرئيسي لفرق المحاسبة، وفيه نظرة سريعة على المؤشرات والحركة اليومية.", "actions": ["مراجعة المؤشرات", "فتح العمليات", "الوصول للتقارير"]},
            {"name": "دليل الحسابات", "path": "/accounts/chart/", "icon": "fa-sitemap", "purpose": "إدارة شجرة الحسابات وإنشاء أو تحديث الحسابات وربطها بالبنية المالية.", "actions": ["عرض الشجرة", "إضافة حساب", "تعديل حساب", "مراجعة التفاصيل"]},
            {"name": "القيود اليومية", "path": "/accounts/journal/", "icon": "fa-book-open", "purpose": "متابعة القيود اليومية والمراجعة والاعتماد والانعكاس عند الحاجة.", "actions": ["عرض القيود", "إنشاء قيد", "ترحيل", "عكس", "حذف"]},
            {"name": "الإيصالات والمصاريف", "path": "/accounts/receipts-expenses/", "icon": "fa-cash-register", "purpose": "مركز متابعة عمليات التحصيل والمصاريف من شاشة واحدة.", "actions": ["فلترة السندات", "فتح الإيصالات", "فتح المصاريف", "مراجعة الحالة"]},
            {"name": "سلف الموظفين", "path": "/accounts/advances/", "icon": "fa-hand-holding-dollar", "purpose": "تسجيل سلف الموظفين ومتابعتها وربطها مع الملفات المالية والرواتب.", "actions": ["عرض السلف", "إضافة سلفة", "فتح التفاصيل"]},
            {"name": "الفترات المحاسبية", "path": "/accounts/periods/", "icon": "fa-calendar-alt", "purpose": "فتح وإغلاق الفترات المحاسبية وضبط العمل الزمني للعمليات المالية.", "actions": ["عرض الفترات", "إنشاء فترة", "إغلاق فترة", "تحديث البيانات"]},
            {"name": "الميزانيات", "path": "/accounts/budgets/", "icon": "fa-chart-pie", "purpose": "إدارة الميزانيات والخطط المالية السنوية أو المرحلية.", "actions": ["عرض الميزانيات", "إضافة ميزانية", "تعديل", "مراجعة التفاصيل"]},
            {"name": "مراكز الكلفة", "path": "/accounts/cost-centers/", "icon": "fa-diagram-project", "purpose": "توزيع ومتابعة المصروفات والإيرادات حسب مراكز الكلفة.", "actions": ["عرض المراكز", "إضافة مركز", "تقرير مالي", "تحليل"]},
            {"name": "مركز التقارير", "path": "/accounts/reports/", "icon": "fa-chart-column", "purpose": "تجميع التقارير المالية التشغيلية والتحليلية ضمن مدخل واحد.", "actions": ["فتح التقارير", "اختيار التقرير", "تصدير"]},
            {"name": "ميزان المراجعة", "path": "/accounts/reports/trial-balance/", "icon": "fa-scale-balanced", "purpose": "عرض رصيد الحسابات والتحقق من التوازن المحاسبي.", "actions": ["فلترة", "عرض النتائج", "تصدير Excel"]},
            {"name": "قائمة الدخل", "path": "/accounts/reports/income-statement/", "icon": "fa-chart-line", "purpose": "تحليل الأرباح والخسائر خلال فترة محددة.", "actions": ["اختيار الفترة", "مراجعة النتائج", "تصدير"]},
            {"name": "الميزانية العمومية", "path": "/accounts/reports/balance-sheet/", "icon": "fa-sheet-plastic", "purpose": "عرض أصول والتزامات وحقوق الملكية حسب الفترة.", "actions": ["فلترة", "تحليل", "تصدير"]},
            {"name": "كشف الحساب", "path": "/accounts/reports/account-statement/", "icon": "fa-book", "purpose": "استعراض حركة حساب محدد لفترة معينة مع التصفية والطباعة.", "actions": ["اختيار حساب", "تحديد المدة", "عرض الحركات", "تصدير"]},
            {"name": "الدورات والمبالغ المستحقة", "path": "/accounts/reports/outstanding-courses/", "icon": "fa-coins", "purpose": "متابعة الدورات ذات الذمم المتأخرة والطلاب المستحقين.", "actions": ["عرض الدورات", "فتح الطلاب", "تصدير التقرير"]},
        ],
    },
    {
        "slug": "administration",
        "title": "الإدارة والرقابة",
        "icon": "fa-shield-halved",
        "audience": "الإدارة العليا",
        "summary": "لوحات الإدارة العامة، الموارد البشرية، المدرسون، الأمان، التقارير العليا، وإدارة كلمات المرور.",
        "features": [
            {"name": "لوحة التحكم الرئيسية", "path": "/pages/index", "icon": "fa-grid-2", "purpose": "عرض المؤشرات العامة وحركة المستخدمين وسجل الأنشطة داخل النظام.", "actions": ["مراجعة النشاط", "فلترة المستخدمين", "تصدير الأنشطة"]},
            {"name": "تقرير النظام", "path": "/pages/system-report/", "icon": "fa-chart-mixed", "purpose": "لوحة عليا للمشرف تتضمن مؤشرات شاملة عن التشغيل والحركة والنتائج.", "actions": ["اختيار اليوم", "توليد التقرير", "الطباعة"]},
            {"name": "التعاميم", "path": "/announcements/", "icon": "fa-bullhorn", "purpose": "إدارة الإعلانات والتنبيهات الداخلية للمستخدمين.", "actions": ["إضافة تعميم", "تحديث", "نشر", "متابعة الظهور"]},
            {"name": "مركز الأمن", "path": "/security/", "icon": "fa-shield-halved", "purpose": "مراقبة السلوك الأمني والتنبيهات والحظر والتتبع.", "actions": ["مراجعة التنبيهات", "إرسال تقرير", "فك الحظر", "تحديث الهوية"]},
            {"name": "المدرسون", "path": "/employ/teachers/", "icon": "fa-chalkboard-user", "purpose": "متابعة ملفات المدرسين وبياناتهم وربطهم بالدوام والحسابات.", "actions": ["عرض المدرسين", "إضافة", "تعديل", "فتح الملف"]},
            {"name": "الموارد البشرية", "path": "/employ/hr/", "icon": "fa-users-gear", "purpose": "إدارة الموظفين والصلاحيات والبيانات الوظيفية.", "actions": ["عرض الموظفين", "إضافة موظف", "تعديل", "متابعة الصلاحيات"]},
            {"name": "إدارة الرواتب", "path": "/employ/salary-management/", "icon": "fa-wallet", "purpose": "متابعة الرواتب والاستحقاقات والخصومات والدفعات.", "actions": ["فتح الرواتب", "مراجعة الصافي", "اعتماد الرواتب"]},
            {"name": "الإجازات", "path": "/employ/vacations/", "icon": "fa-umbrella-beach", "purpose": "إدارة طلبات الإجازة وسجلاتها وتتبع حالتها.", "actions": ["عرض الطلبات", "إضافة إجازة", "اعتماد أو تعديل"]},
            {"name": "المواد الدراسية", "path": "/courses/subjects/", "icon": "fa-book-open-reader", "purpose": "إدارة المواد الدراسية الرئيسية المعتمدة داخل النظام.", "actions": ["عرض المواد", "إضافة مادة", "تعديل", "حذف"]},
            {"name": "إدارة كلمات المرور", "path": "/registration/superuser-password-reset/", "icon": "fa-key", "purpose": "أداة إدارية لإعادة تهيئة كلمات المرور وإرسال التعليمات للمستخدمين.", "actions": ["طلب إعادة التعيين", "نسخ الكود", "إرسال عبر واتساب"]},
        ],
    },
]


USER_GUIDE_WORKFLOWS = [
    {"title": "مسار موظف الاستقبال", "steps": ["فتح بوابة النظام أو قائمة الطلاب السريعين حسب نوع الخدمة.", "إضافة الطالب أو البحث عنه إذا كان موجوداً مسبقاً.", "تسجيله في الدورة المناسبة أو فتح ملفه الشخصي.", "إصدار الإيصال المباشر أو تثبيت الدفعة الأولى."]},
    {"title": "مسار التوجيه", "steps": ["مراجعة الدورات أو الشعب المفتوحة.", "تحليل التقاطعات أو استخدام الفرز اليدوي عند وجود ازدحام.", "ربط الطلاب بالجلسات الصحيحة ومتابعة الحضور.", "العودة إلى لوحة العلامات أو تقارير الحضور عند الحاجة."]},
    {"title": "مسار المحاسب", "steps": ["الدخول إلى لوحة المحاسبة ثم فتح العملية المطلوبة.", "تسجيل قيد أو سند أو مراجعة الذمم المتأخرة.", "التحقق من الفترة المحاسبية ومركز الكلفة إن لزم.", "استخراج التقرير أو التصدير في نهاية الإجراء."]},
    {"title": "مسار الإدارة", "steps": ["متابعة لوحة التحكم العامة وسجل النشاط.", "فتح مركز الأمن أو تقرير النظام لمراجعة الحالة التشغيلية.", "مراجعة الموارد البشرية والرواتب والتعاميم.", "التدخل في كلمات المرور أو الصلاحيات عند وجود حالة خاصة."]},
]


USER_GUIDE_SCREENSHOTS = [
    {"title": "القائمة الجانبية الموحدة", "path": static("img/user-guide/sidebar-overview.png"), "caption": "مركز التنقل الرئيسي لجميع أقسام النظام.", "module": "reception", "priority": 1},
    {"title": "صفحة الطلاب السريعين", "path": static("img/user-guide/quick-students-list.png"), "caption": "واجهة مناسبة للاستقبال والتسجيلات السريعة.", "module": "reception", "priority": 2},
    {"title": "واجهة الدورات السريعة", "path": static("img/user-guide/quick-courses-list.png"), "caption": "مركز إدارة الدورات والجلسات والجداول.", "module": "guidance", "priority": 1},
    {"title": "إدارة الحضور", "path": static("img/user-guide/attendance-overview.png"), "caption": "صفحة متابعة حضور الطلاب والحصص.", "module": "guidance", "priority": 2},
    {"title": "لوحة المحاسبة", "path": static("img/user-guide/accounts-dashboard.png"), "caption": "مدخل العمليات المالية والتقارير والتحصيل.", "module": "accounting", "priority": 1},
    {"title": "مركز التقارير المالية", "path": static("img/user-guide/accounts-reports.png"), "caption": "وصول سريع إلى أهم التقارير المالية.", "module": "accounting", "priority": 2},
    {"title": "لوحة التحكم العامة", "path": static("img/user-guide/dashboard-overview.png"), "caption": "واجهة متابعة النشاط والمؤشرات العامة للإدارة.", "module": "administration", "priority": 1},
    {"title": "إدارة الموارد البشرية", "path": static("img/user-guide/hr-overview.png"), "caption": "واجهة الموظفين والرواتب والإجازات.", "module": "administration", "priority": 2},
]


def build_user_guide_context():
    screenshot_map = {}
    for shot in USER_GUIDE_SCREENSHOTS:
        screenshot_map.setdefault(shot["module"], []).append(shot)

    modules = []
    for module in USER_GUIDE_MODULES:
        module_copy = dict(module)
        module_copy["screenshots"] = sorted(screenshot_map.get(module["slug"], []), key=lambda item: item.get("priority", 99))
        module_copy["feature_total"] = len(module["features"])
        modules.append(module_copy)

    total_features = sum(len(module["features"]) for module in USER_GUIDE_MODULES)
    total_actions = sum(len(feature["actions"]) for module in USER_GUIDE_MODULES for feature in module["features"])
    return {
        "guide_modules": modules,
        "guide_workflows": USER_GUIDE_WORKFLOWS,
        "guide_screenshots": USER_GUIDE_SCREENSHOTS,
        "guide_module_count": len(USER_GUIDE_MODULES),
        "guide_feature_count": total_features,
        "guide_action_count": total_actions,
    }
