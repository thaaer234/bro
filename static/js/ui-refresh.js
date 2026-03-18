document.addEventListener('DOMContentLoaded', () => {
    const sidebar = document.querySelector('.sidebar');
    const toggleButton = document.querySelector('.mobile-menu-toggle');
    const menuGroups = document.querySelectorAll('.menu-group');

    window.toggleSidebar = function toggleSidebar() {
        if (!sidebar) {
            return;
        }
        sidebar.classList.toggle('is-open');
        document.body.classList.toggle('sidebar-open', sidebar.classList.contains('is-open'));
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

        title.addEventListener('click', () => {
            group.classList.toggle('expanded');
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
        }
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && sidebar) {
            sidebar.classList.remove('is-open');
            document.body.classList.remove('sidebar-open');
        }
    });
});
