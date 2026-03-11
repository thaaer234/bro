from pathlib import Path
content = """{% extends "base.html" %}
{% load static %}

{% block content %}
<div class="page register-page">
    <div class="page-header">
        <div class="page-header__left">
            <div class="page-header__icon"><i class="fas fa-book-open"></i></div>
            <div>
                <h1 class="page-title">تسجيل طلاب سريع</h1>
                <p class="page-subtitle">اختر الدورات المطلوبة للطالب {{ student.full_name }}</p>
            </div>
        </div>
        <a href="{% url 'quick:student_profile' student.id %}" class="btn btn--ghost">
            <i class="fas fa-arrow-right"></i>
            <span>عرض الملف</span>
        </a>
    </div>

    <div class="card">
        <div class="card-body">
            <div class="summary-panel">
                <div>
                    <p class="summary-label">إجمالي المطلوب</p>
                    <p class="summary-total">
                        <span id="selected-total">0</span> ل.س
                    </p>
                </div>
                <div>
                    <p class="summary-label">عدد الدورات المختارة</p>
                    <p class="summary-count"><span id="selected-count">0</span> دورة</p>
                </div>
                <div class="summary-hint">
                    اختر الدورات التي سيدفع عنها الطالب أو حدد خيار الدفع الكامل لكل دورة لإنشاء إيصال خاص بها.
                </div>
            </div>

            {% if courses %}
            <form method="POST" action="{% url 'quick:register_quick_course' student.id %}">
                {% csrf_token %}
                <div class="course-grid">
                    {% for course in courses %}
                    <div class="course-card">
                        <input type="checkbox" name="course_ids" value="{{ course.id }}" class="course-selector" data-price="{{ course.price }}">
                        <div class="course-card__body">
                            <div class="course-card__head">
                                <h5>{{ course.name }}</h5>
                                <span class="course-tag">{{ course.get_course_type_display }}</span>
                            </div>
                            <ul class="course-meta">
                                <li><strong>السعر:</strong> {{ course.price|floatformat:0 }} ل.س</li>
                                <li><strong>المدة:</strong> {{ course.duration_weeks }} أسابيع</li>
                                <li><strong>ساعات / أسبوع:</strong> {{ course.hours_per_week }}</li>
                            </ul>
                            {% if course.description %}
                            <p class="course-description">{{ course.description|truncatewords:16 }}</p>
                            {% endif %}
                            <div class="form-group pay-full-group">
                                <input type="checkbox" name="pay_full_{{ course.id }}" value="1" id="pay-full-{{ course.id }}" class="pay-full-checkbox" disabled>
                                <label for="pay-full-{{ course.id }}">دفع كامل وإنشاء إيصال</label>
                            </div>
                        </div>
                    </div>
                    {% endfor %}
                </div>
                <div class="form-actions">
                    <button type="submit" class="btn btn-primary">
                        حفظ التسجيل وإنشاء القيود
                    </button>
                </div>
            </form>
            {% else %}
            <div class="empty-state">
                <div class="empty-icon"><i class="fas fa-book"></i></div>
                <h4>لا توجد دورات متاحة</h4>
                <p>تأكد من إعداد الدورات للعام الدراسي الحالي.</p>
            </div>
            {% endif %}
        </div>
    </div>
</div>
{% endblock %}

<style>
.summary-panel {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
    padding: 18px 16px;
    border: 1px solid #e3e6ea;
    border-radius: 10px;
    margin-bottom: 18px;
    background: #fff;
}
.summary-total {
    font-size: 30px;
    font-weight: 700;
    margin: 0;
}
.summary-count {
    font-size: 18px;
    font-weight: 600;
    margin: 0;
}
.summary-label {
    font-size: 13px;
    color: #6c757d;
    margin: 0 0 8px;
}
.summary-hint {
    font-size: 13px;
    color: #495057;
    align-self: center;
}
.course-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 16px;
}
.course-card {
    border: 1px solid #dde3ea;
    border-radius: 12px;
    padding: 14px;
    background: #fff;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    min-height: 220px;
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.05);
    position: relative;
}
.course-card__body {
    display: flex;
    flex-direction: column;
    gap: 10px;
}
.course-card__head {
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.course-card__head h5 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
}
.course-tag {
    font-size: 12px;
    padding: 4px 10px;
    border-radius: 999px;
    background: #f1f3f5;
    color: #495057;
}
.course-meta {
    list-style: none;
    padding: 0;
    margin: 0;
    font-size: 13px;
    color: #4a5663;
}
.course-meta li {
    margin-bottom: 4px;
}
.course-description {
    font-size: 12px;
    color: #6c757d;
    margin: 0;
}
.pay-full-group {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
}
.course-card input[type="checkbox"] {
    position: absolute;
    top: 12px;
    right: 12px;
    width: 18px;
    height: 18px;
    accent-color: #1d7cf0;
}
.form-actions {
    margin-top: 20px;
    text-align: center;
}
.empty-state {
    padding: 50px 20px;
    text-align: center;
}
.empty-icon {
    font-size: 60px;
    color: #ced4da;
    margin-bottom: 12px;
}
@media (max-width: 768px) {
    .summary-panel {
        grid-template-columns: 1fr;
    }
    .course-card {
        min-height: 190px;
    }
}
</style>

<script>
document.addEventListener('DOMContentLoaded', () => {
    const totalEl = document.getElementById('selected-total');
    const countEl = document.getElementById('selected-count');
    const summaryHint = document.querySelector('.summary-hint');

    function updateSummary() {
        let total = 0;
        let selectedCount = 0;

        document.querySelectorAll('.course-selector').forEach(checkbox => {
            const price = parseFloat(checkbox.dataset.price || '0');
            const payFull = document.getElementById(`pay-full-${checkbox.value}`);

            if (checkbox.checked) {
                selectedCount += 1;
                total += price;
                if (payFull) {
                    payFull.disabled = false;
                }
            } else if (payFull) {
                payFull.disabled = true;
                payFull.checked = false;
            }
        });

        totalEl.textContent = total.toLocaleString('en-US', { minimumFractionDigits: 0 });
        countEl.textContent = selectedCount;

        if (selectedCount === 0) {
            summaryHint.textContent = 'اختر دورة واحدة على الأقل للمتابعة.';
        } else {
            summaryHint.textContent = 'حدد خيار "دفع كامل" لكل دورة لإنشاء إيصال عند الحاجة.';
        }
    }

    document.querySelectorAll('.course-selector').forEach(checkbox => {
        checkbox.addEventListener('change', updateSummary);
    });

    updateSummary();
});
</script>
"""
Path('templates/quick/register_quick_course.html').write_text(content, encoding='utf-8')
