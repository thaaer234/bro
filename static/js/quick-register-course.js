document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('quick-register-form');
    if (!form) return;

    const catalogNode = document.getElementById('quick-course-session-catalog');
    const sessionCatalog = catalogNode ? JSON.parse(catalogNode.textContent || '{}') : {};
    const searchInput = document.getElementById('course-search');
    const typeFilter = document.getElementById('course-type-filter');
    const visibilityFilter = document.getElementById('course-visibility-filter');
    const totalEl = document.getElementById('selected-total');
    const countEl = document.getElementById('selected-count');
    const selectedSessionsCountEl = document.getElementById('selected-sessions-count');
    const noteEl = document.getElementById('quick-register-note');
    const submitHintEl = document.getElementById('quick-register-submit-hint');
    const courseCards = Array.from(document.querySelectorAll('.quick-register-course'));
    const formatter = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });

    const modal = document.getElementById('quick-session-modal');
    const modalTitle = document.getElementById('quick-session-modal-title');
    const modalSubtitle = document.getElementById('quick-session-modal-subtitle');
    const modalBody = document.getElementById('quick-session-modal-body');
    const modalError = document.getElementById('quick-session-modal-error');
    const closeModalBtn = document.getElementById('quick-session-modal-close');
    const clearModalBtn = document.getElementById('quick-session-clear-btn');
    const applyModalBtn = document.getElementById('quick-session-apply-btn');

    let activeCourseId = null;
    let draftSessionId = null;

    function populateTypeFilter() {
        const seen = new Set();
        courseCards.forEach((card) => {
            const type = card.dataset.courseType;
            const typeLabel = card.dataset.courseTypeLabel;
            if (!type || !typeLabel || seen.has(type)) return;
            seen.add(type);
            const option = document.createElement('option');
            option.value = type;
            option.textContent = typeLabel;
            typeFilter.appendChild(option);
        });
    }

    function getCourseCard(courseId) {
        return document.querySelector(`.quick-register-course[data-course-id="${courseId}"]`);
    }

    function getCourseState(card) {
        return {
            checkbox: card.querySelector('.js-course-checkbox'),
            payFull: card.querySelector('.js-pay-full'),
            sessionInput: card.querySelector('.js-session-id'),
            sessionSummary: card.querySelector('.js-session-summary'),
            selectBtn: card.querySelector('.js-select-session-btn'),
            hasSessions: card.dataset.hasSessions === 'true',
            isLocked: card.dataset.locked === 'true'
        };
    }

    function getSelectedSessionData(courseId) {
        const card = getCourseCard(courseId);
        if (!card) return null;
        const { sessionInput } = getCourseState(card);
        const selectedId = sessionInput ? sessionInput.value : '';
        const courseSessions = sessionCatalog[String(courseId)] || [];
        return courseSessions.find((session) => String(session.id) === String(selectedId)) || null;
    }

    function setSessionSummary(card) {
        const { checkbox, sessionSummary, hasSessions, isLocked } = getCourseState(card);
        if (!sessionSummary || isLocked) return;

        const selectedSession = getSelectedSessionData(card.dataset.courseId);
        sessionSummary.classList.remove('is-empty', 'is-required');

        if (!checkbox.checked) {
            sessionSummary.classList.add('is-empty');
            sessionSummary.innerHTML = '<i class="fas fa-school"></i><div>لم يتم اختيار كلاس بعد.</div>';
            return;
        }

        if (selectedSession) {
            sessionSummary.innerHTML = `
                <i class="fas fa-check-circle"></i>
                <div>
                    <strong>${selectedSession.title}</strong><br>
                    <small>${selectedSession.date_range} | ${selectedSession.time_range}</small>
                </div>
            `;
            return;
        }

        if (hasSessions) {
            sessionSummary.classList.add('is-required');
            sessionSummary.innerHTML = '<i class="fas fa-triangle-exclamation"></i><div>الدورة محددة ولكن ما زال اختيار الكلاس مطلوبًا.</div>';
            return;
        }

        sessionSummary.classList.add('is-empty');
        sessionSummary.innerHTML = '<i class="fas fa-circle-info"></i><div>لا توجد كلاسات مفعلة لهذه الدورة حاليًا، وسيبقى الطالب غير منزل.</div>';
    }

    function updateCardState(card) {
        const { checkbox, payFull, sessionInput, selectBtn, isLocked } = getCourseState(card);
        if (isLocked || !checkbox) return;

        card.classList.toggle('is-selected', checkbox.checked);

        if (payFull) {
            payFull.disabled = !checkbox.checked;
            if (checkbox.checked) {
                payFull.checked = true;
            } else {
                payFull.checked = false;
            }
        }

        if (!checkbox.checked && sessionInput) {
            sessionInput.value = '';
        }

        if (selectBtn) {
            selectBtn.innerHTML = checkbox.checked
                ? '<i class="fas fa-school"></i><span>اختيار أو تعديل الكلاس</span>'
                : '<i class="fas fa-school"></i><span>اختيار الكلاس</span>';
        }

        setSessionSummary(card);
    }

    function updateSummary() {
        let total = 0;
        let selectedCount = 0;
        let selectedSessionsCount = 0;
        let missingRequiredSession = 0;

        courseCards.forEach((card) => {
            const { checkbox, sessionInput, hasSessions, isLocked } = getCourseState(card);
            if (isLocked || !checkbox || !checkbox.checked) return;

            selectedCount += 1;
            total += Number(card.dataset.coursePrice || 0);

            if (sessionInput && sessionInput.value) {
                selectedSessionsCount += 1;
            } else if (hasSessions) {
                missingRequiredSession += 1;
            }
        });

        totalEl.textContent = formatter.format(total);
        countEl.textContent = selectedCount;
        selectedSessionsCountEl.textContent = selectedSessionsCount;

        if (selectedCount === 0) {
            noteEl.textContent = 'لم يتم اختيار أي دورة بعد. ابدأ من البطاقات على اليسار، ثم ثبت الكلاس عند الحاجة.';
            submitHintEl.textContent = 'إذا اخترت دورة وفيها كلاسات متاحة، يجب تثبيت الكلاس قبل إرسال النموذج.';
            return;
        }

        if (missingRequiredSession > 0) {
            noteEl.textContent = `هناك ${missingRequiredSession} دورة محددة ما زالت تحتاج اختيار كلاس قبل الحفظ.`;
            submitHintEl.textContent = 'يوجد دورات محددة بدون كلاس مختار. راجع البطاقات ذات التنبيه الأحمر.';
            return;
        }

        noteEl.textContent = `جاهز للحفظ: ${selectedCount} دورة محددة، وتم تثبيت ${selectedSessionsCount} اختيار كلاس.`;
        submitHintEl.textContent = 'النموذج جاهز. يمكنك الحفظ الآن أو تعديل أي كلاس قبل الإرسال.';
    }

    function applyFilters() {
        const query = (searchInput.value || '').trim().toLowerCase();
        const selectedType = typeFilter.value || 'all';
        const visibility = visibilityFilter.value || 'all';

        courseCards.forEach((card) => {
            const matchesQuery =
                !query ||
                (card.dataset.courseName || '').includes(query) ||
                (card.dataset.courseDescription || '').includes(query) ||
                (card.dataset.courseTypeLabel || '').toLowerCase().includes(query);
            const matchesType = selectedType === 'all' || card.dataset.courseType === selectedType;
            const locked = card.dataset.locked === 'true';
            const matchesVisibility =
                visibility === 'all' ||
                (visibility === 'available' && !locked) ||
                (visibility === 'locked' && locked);

            card.style.display = matchesQuery && matchesType && matchesVisibility ? '' : 'none';
        });
    }

    function openModal(courseId) {
        const courseCard = getCourseCard(courseId);
        if (!courseCard) return;
        const titleNode = courseCard.querySelector('.quick-register-course__title');
        const titleText = titleNode ? titleNode.textContent.trim() : '';

        const courseSessions = sessionCatalog[String(courseId)] || [];
        const selectedSession = getSelectedSessionData(courseId);
        activeCourseId = String(courseId);
        draftSessionId = selectedSession ? String(selectedSession.id) : '';
        modalError.textContent = '';

        modalTitle.textContent = `كلاسات دورة ${titleText}`;
        modalSubtitle.textContent = courseSessions.length
            ? 'اختر الكلاس الذي تريد تنزيل الطالب عليه مباشرة ضمن هذه الدورة.'
            : 'لا توجد كلاسات نشطة لهذه الدورة حاليًا.';

        if (!courseSessions.length) {
            modalBody.innerHTML = `
                <div class="quick-register-empty">
                    <div class="quick-register-empty__icon"><i class="fas fa-school"></i></div>
                    <h3 class="quick-register-section__title">لا توجد كلاسات متاحة الآن</h3>
                    <p>يمكنك تسجيل الدورة الآن، لكن الطالب سيبقى ضمن غير المنزلين إلى حين فتح كلاس مناسب.</p>
                </div>
            `;
            clearModalBtn.style.display = 'none';
            applyModalBtn.style.display = 'none';
        } else {
            clearModalBtn.style.display = '';
            applyModalBtn.style.display = '';
            modalBody.innerHTML = `
                <div class="quick-register-session-list">
                    ${courseSessions.map((session) => {
                        const selectedClass = String(session.id) === String(draftSessionId) ? 'is-selected' : '';
                        const fullClass = session.is_full ? 'is-full' : '';
                        const capacityLabel = session.capacity
                            ? `${session.assigned_count} / ${session.capacity}`
                            : `${session.assigned_count} / مفتوح`;
                        const fullBadge = session.is_full ? '<span class="quick-register-badge quick-register-badge--muted"><i class="fas fa-lock"></i> ممتلئ</span>' : '';

                        return `
                            <label class="quick-register-session ${selectedClass} ${fullClass}" data-session-id="${session.id}">
                                <input type="radio" name="modal-session-choice" class="quick-register-session__radio" value="${session.id}" ${selectedClass ? 'checked' : ''} ${session.is_full ? 'disabled' : ''}>
                                <div>
                                    <h3 class="quick-register-session__title">${session.title}</h3>
                                    <div class="quick-register-session__meta">
                                        <span><i class="fas fa-calendar-days"></i>${session.date_range}</span>
                                        <span><i class="fas fa-clock"></i>${session.time_range}</span>
                                        <span><i class="fas fa-repeat"></i>${session.meeting_days}</span>
                                        <span><i class="fas fa-door-open"></i>${session.room_name}</span>
                                        ${fullBadge}
                                    </div>
                                </div>
                                <div class="quick-register-session__capacity">
                                    <span class="quick-register-stat__label">الطلاب / السعة</span>
                                    <strong>${capacityLabel}</strong>
                                </div>
                            </label>
                        `;
                    }).join('')}
                </div>
            `;
        }

        modal.hidden = false;
        document.body.style.overflow = 'hidden';
    }

    function closeModal() {
        modal.hidden = true;
        activeCourseId = null;
        draftSessionId = null;
        modalBody.innerHTML = '';
        modalError.textContent = '';
        document.body.style.overflow = '';
    }

    function commitSelectedSession(sessionId) {
        if (!activeCourseId) return;
        const card = getCourseCard(activeCourseId);
        if (!card) return;
        const { checkbox, sessionInput } = getCourseState(card);
        if (!checkbox || !checkbox.checked || !sessionInput) return;
        sessionInput.value = sessionId || '';
        setSessionSummary(card);
        updateSummary();
        closeModal();
    }

    function activateCourseCard(card, openClasses) {
        const { checkbox, isLocked } = getCourseState(card);
        if (isLocked || !checkbox) return;

        if (!checkbox.checked) {
            checkbox.checked = true;
            updateCardState(card);
            updateSummary();
        }

        if (openClasses && card.dataset.hasSessions === 'true') {
            openModal(card.dataset.courseId);
        }
    }

    courseCards.forEach((card) => {
        const { checkbox, selectBtn, isLocked } = getCourseState(card);
        if (isLocked) return;

        updateCardState(card);

        card.addEventListener('click', function (event) {
            const interactiveTarget = event.target.closest('button, a, label.quick-register-pay, .js-pay-full');
            if (interactiveTarget) return;
            activateCourseCard(card, true);
        });

        if (checkbox) {
            checkbox.addEventListener('click', function (event) {
                event.stopPropagation();
            });

            checkbox.addEventListener('change', function () {
                updateCardState(card);
                updateSummary();
                if (this.checked && card.dataset.hasSessions === 'true' && !card.querySelector('.js-session-id').value) {
                    openModal(card.dataset.courseId);
                }
            });
        }

        if (selectBtn) {
            selectBtn.addEventListener('click', function () {
                activateCourseCard(card, true);
            });
        }
    });

    modalBody.addEventListener('change', function (event) {
        if (!event.target.matches('.quick-register-session__radio')) return;
        draftSessionId = event.target.value;
        modalBody.querySelectorAll('.quick-register-session').forEach((item) => {
            item.classList.toggle('is-selected', item.dataset.sessionId === draftSessionId);
        });
    });

    if (applyModalBtn) {
        applyModalBtn.addEventListener('click', function () {
            if (!draftSessionId) {
                modalError.textContent = 'اختر كلاسًا أولًا قبل التثبيت.';
                return;
            }
            commitSelectedSession(draftSessionId);
        });
    }

    if (clearModalBtn) {
        clearModalBtn.addEventListener('click', function () {
            commitSelectedSession('');
        });
    }

    if (closeModalBtn) {
        closeModalBtn.addEventListener('click', closeModal);
    }

    if (modal) {
        modal.addEventListener('click', function (event) {
            if (event.target === modal) closeModal();
        });
    }

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' && modal && !modal.hidden) closeModal();
    });

    form.addEventListener('submit', function (event) {
        const missingSessionCards = [];

        courseCards.forEach((card) => {
            const { checkbox, sessionInput, hasSessions, isLocked } = getCourseState(card);
            if (isLocked || !checkbox || !checkbox.checked) return;
            if (hasSessions && !(sessionInput && sessionInput.value)) {
                missingSessionCards.push(card);
                setSessionSummary(card);
            }
        });

        if (missingSessionCards.length) {
            event.preventDefault();
            noteEl.textContent = `لا يمكن الحفظ الآن لأن ${missingSessionCards.length} دورة محددة تحتاج اختيار كلاس.`;
            missingSessionCards[0].scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    });

    if (searchInput) searchInput.addEventListener('input', applyFilters);
    if (typeFilter) typeFilter.addEventListener('change', applyFilters);
    if (visibilityFilter) visibilityFilter.addEventListener('change', applyFilters);

    populateTypeFilter();
    applyFilters();
    updateSummary();
});
