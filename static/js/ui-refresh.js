document.addEventListener('DOMContentLoaded', () => {
    const sidebar = document.querySelector('.sidebar');
    const toggleButton = document.querySelector('.mobile-menu-toggle');
    const menuGroups = document.querySelectorAll('.menu-group');

    window.toggleSidebar = function toggleSidebar() {
        if (!sidebar) {
            return;
        }
        sidebar.classList.toggle('is-open');
        const isOpen = sidebar.classList.contains('is-open');
        document.body.classList.toggle('sidebar-open', isOpen);
        if (toggleButton) {
            toggleButton.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        }
    };

    if (toggleButton) {
        toggleButton.addEventListener('click', window.toggleSidebar);
    }

    menuGroups.forEach((group) => {
        const title = group.querySelector('.menu-group-title');
        if (!title) {
            return;
        }

        if (group.querySelector('.menu-item.active')) {
            group.classList.add('expanded');
        }
        title.setAttribute('aria-expanded', group.classList.contains('expanded') ? 'true' : 'false');

        title.addEventListener('click', () => {
            group.classList.toggle('expanded');
            title.setAttribute('aria-expanded', group.classList.contains('expanded') ? 'true' : 'false');
        });
    });

    document.addEventListener('click', (event) => {
        if (!sidebar || window.innerWidth > 767) {
            return;
        }

        const clickedInsideSidebar = sidebar.contains(event.target);
        const clickedToggle = toggleButton && toggleButton.contains(event.target);

        if (!clickedInsideSidebar && !clickedToggle) {
            sidebar.classList.remove('is-open');
            document.body.classList.remove('sidebar-open');
            if (toggleButton) {
                toggleButton.setAttribute('aria-expanded', 'false');
            }
        }
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && sidebar) {
            sidebar.classList.remove('is-open');
            document.body.classList.remove('sidebar-open');
            if (toggleButton) {
                toggleButton.setAttribute('aria-expanded', 'false');
                toggleButton.focus();
            }
        }
    });
});
