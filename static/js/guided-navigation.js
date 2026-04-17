(function () {
    function onReady(callback) {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', callback, { once: true });
            return;
        }
        callback();
    }

    function isVisible(element) {
        if (!element) {
            return false;
        }
        var rect = element.getBoundingClientRect();
        var style = window.getComputedStyle(element);
        return !!(rect.width || rect.height) && style.visibility !== 'hidden' && style.display !== 'none';
    }

    function findVisible(selectors) {
        if (!selectors) {
            return null;
        }
        for (var i = 0; i < selectors.length; i += 1) {
            var nodeList = document.querySelectorAll(selectors[i]);
            for (var j = 0; j < nodeList.length; j += 1) {
                if (isVisible(nodeList[j])) {
                    return nodeList[j];
                }
            }
        }
        return null;
    }

    function resolveAliasTarget(alias) {
        if (alias === '@primary-action') {
            return findVisible([
                '[data-guide-key]',
                '.btn.btn-primary',
                'button[type="submit"]',
                'a.btn-primary',
                '.accounts-quick-card',
            ]);
        }
        if (alias === '@first-field') {
            return findVisible([
                'form input:not([type="hidden"]):not([disabled])',
                'form select:not([disabled])',
                'form textarea:not([disabled])',
            ]);
        }
        if (alias === '@search') {
            return findVisible([
                'input[type="search"]',
                'input[placeholder*="ابحث"]',
                'input[placeholder*="بحث"]',
                'input[type="text"]',
            ]);
        }
        if (alias === '@table-action') {
            return findVisible([
                'table .btn',
                '.quick-actions-cell .btn',
                '.action-buttons .btn',
            ]);
        }
        return null;
    }

    function resolveTarget(rawTarget) {
        if (!rawTarget) {
            return resolveAliasTarget('@primary-action');
        }
        if (rawTarget.charAt(0) === '@') {
            return resolveAliasTarget(rawTarget);
        }
        try {
            return findVisible([rawTarget]);
        } catch (error) {
            return null;
        }
    }

    function cleanupUrl(params) {
        var url = new URL(window.location.href);
        params.forEach(function (key) {
            url.searchParams.delete(key);
        });
        window.history.replaceState({}, document.title, url.pathname + url.search + url.hash);
    }

    function openModalIfNeeded(params) {
        var modalId = params.get('guide_modal');
        if (!modalId) {
            return;
        }
        var modalElement = document.getElementById(modalId);
        if (!modalElement) {
            return;
        }
        if (window.bootstrap && window.bootstrap.Modal) {
            window.bootstrap.Modal.getOrCreateInstance(modalElement).show();
            return;
        }
        modalElement.classList.add('show');
        modalElement.style.display = 'block';
        modalElement.removeAttribute('aria-hidden');
    }

    function attachGuide(params) {
        if (!params.get('guide') && !params.get('guide_target')) {
            return;
        }

        var guideTarget = params.get('guide_target') || '@primary-action';
        var title = params.get('guide_title') || 'خطوة موجهة';
        var message = params.get('guide_message') || 'اتبع العنصر المضيء لإكمال الخطوة التالية.';
        var duration = parseInt(params.get('guide_duration') || '10000', 10);
        if (!Number.isFinite(duration) || duration < 1500) {
            duration = 10000;
        }

        openModalIfNeeded(params);

        var attempts = 0;
        var maxAttempts = 20;
        var timer = window.setInterval(function () {
            attempts += 1;
            var target = resolveTarget(guideTarget);
            if (!target && attempts < maxAttempts) {
                return;
            }
            window.clearInterval(timer);
            if (!target) {
                cleanupUrl(['guide', 'guide_target', 'guide_title', 'guide_message', 'guide_duration', 'guide_modal']);
                return;
            }

            target.classList.add('app-guide-target-live');
            if (typeof target.scrollIntoView === 'function') {
                target.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'center' });
            }

            var overlay = document.createElement('div');
            overlay.className = 'app-guide-overlay';
            overlay.innerHTML =
                '<div class="app-guide-shade app-guide-shade--top"></div>' +
                '<div class="app-guide-shade app-guide-shade--right"></div>' +
                '<div class="app-guide-shade app-guide-shade--bottom"></div>' +
                '<div class="app-guide-shade app-guide-shade--left"></div>' +
                '<div class="app-guide-spotlight"></div>' +
                '<div class="app-guide-popup" role="dialog" aria-live="polite">' +
                    '<span class="app-guide-popup__badge"><i class="fas fa-location-arrow"></i> توجيه تفاعلي</span>' +
                    '<h3 class="app-guide-popup__title"></h3>' +
                    '<p class="app-guide-popup__body"></p>' +
                    '<div class="app-guide-popup__footer"><span>سيختفي تلقائياً خلال ثوانٍ قليلة</span><strong></strong></div>' +
                '</div>' +
                '<div class="app-guide-tooltip" data-placement="bottom" aria-hidden="true">' +
                    '<h4 class="app-guide-tooltip__title"></h4>' +
                    '<p class="app-guide-tooltip__body"></p>' +
                '</div>';
            document.body.appendChild(overlay);

            var spotlight = overlay.querySelector('.app-guide-spotlight');
            var shadeTop = overlay.querySelector('.app-guide-shade--top');
            var shadeRight = overlay.querySelector('.app-guide-shade--right');
            var shadeBottom = overlay.querySelector('.app-guide-shade--bottom');
            var shadeLeft = overlay.querySelector('.app-guide-shade--left');
            var popupTitle = overlay.querySelector('.app-guide-popup__title');
            var popupBody = overlay.querySelector('.app-guide-popup__body');
            var popupCountdown = overlay.querySelector('.app-guide-popup__footer strong');
            var tooltip = overlay.querySelector('.app-guide-tooltip');
            var tooltipTitle = overlay.querySelector('.app-guide-tooltip__title');
            var tooltipBody = overlay.querySelector('.app-guide-tooltip__body');

            popupTitle.textContent = title;
            popupBody.textContent = message;
            tooltipTitle.textContent = 'العنصر المطلوب هنا';
            tooltipBody.textContent = message;

            function placeGuide() {
                var rect = target.getBoundingClientRect();
                var holeTop = Math.max(0, rect.top - 10);
                var holeLeft = Math.max(0, rect.left - 10);
                var holeWidth = Math.min(window.innerWidth - holeLeft, rect.width + 20);
                var holeHeight = Math.min(window.innerHeight - holeTop, rect.height + 20);
                var holeRight = holeLeft + holeWidth;
                var holeBottom = holeTop + holeHeight;

                shadeTop.style.top = '0px';
                shadeTop.style.left = '0px';
                shadeTop.style.width = '100vw';
                shadeTop.style.height = holeTop + 'px';

                shadeBottom.style.top = holeBottom + 'px';
                shadeBottom.style.left = '0px';
                shadeBottom.style.width = '100vw';
                shadeBottom.style.height = Math.max(0, window.innerHeight - holeBottom) + 'px';

                shadeLeft.style.top = holeTop + 'px';
                shadeLeft.style.left = '0px';
                shadeLeft.style.width = holeLeft + 'px';
                shadeLeft.style.height = holeHeight + 'px';

                shadeRight.style.top = holeTop + 'px';
                shadeRight.style.left = holeRight + 'px';
                shadeRight.style.width = Math.max(0, window.innerWidth - holeRight) + 'px';
                shadeRight.style.height = holeHeight + 'px';

                spotlight.style.top = holeTop + 'px';
                spotlight.style.left = holeLeft + 'px';
                spotlight.style.width = holeWidth + 'px';
                spotlight.style.height = holeHeight + 'px';

                var tooltipWidth = Math.max(tooltip.offsetWidth || 0, tooltip.getBoundingClientRect().width || 0, 280);
                var tooltipHeight = Math.max(tooltip.offsetHeight || 0, tooltip.getBoundingClientRect().height || 0, 110);
                var tooltipLeft = rect.left + (rect.width / 2) - (tooltipWidth / 2);
                tooltipLeft = Math.max(16, Math.min(window.innerWidth - tooltipWidth - 16, tooltipLeft));

                var tooltipTop = rect.bottom + 18;
                var placement = 'bottom';
                if (rect.bottom + tooltipHeight + 24 > window.innerHeight) {
                    tooltipTop = rect.top - tooltipHeight - 18;
                    placement = 'top';
                }
                tooltip.dataset.placement = placement;
                tooltip.style.top = Math.max(16, tooltipTop) + 'px';
                tooltip.style.left = tooltipLeft + 'px';
            }

            var startedAt = Date.now();
            function updateCountdown() {
                var remaining = Math.max(0, duration - (Date.now() - startedAt));
                popupCountdown.textContent = Math.ceil(remaining / 1000) + ' ث';
            }

            function destroyGuide() {
                target.classList.remove('app-guide-target-live');
                window.removeEventListener('resize', placeGuide);
                window.removeEventListener('scroll', placeGuide, true);
                if (overlay.parentNode) {
                    overlay.parentNode.removeChild(overlay);
                }
                cleanupUrl(['guide', 'guide_target', 'guide_title', 'guide_message', 'guide_duration', 'guide_modal']);
            }

            placeGuide();
            updateCountdown();
            window.addEventListener('resize', placeGuide);
            window.addEventListener('scroll', placeGuide, true);

            var countdownInterval = window.setInterval(updateCountdown, 250);
            window.setTimeout(function () {
                window.clearInterval(countdownInterval);
                destroyGuide();
            }, duration);
        }, 180);
    }

    onReady(function () {
        attachGuide(new URLSearchParams(window.location.search));
    });
})();
