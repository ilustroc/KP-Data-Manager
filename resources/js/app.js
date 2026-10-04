const sidebarButton = document.querySelector('[data-sidebar-toggle]');
const sidebar = document.querySelector('[data-sidebar]');
const sidebarOverlay = document.querySelector('[data-sidebar-overlay]');

const setSidebarOpen = (isOpen) => {
    if (! sidebar || ! sidebarButton || ! sidebarOverlay) {
        return;
    }

    sidebar.classList.toggle('-translate-x-full', ! isOpen);
    sidebarOverlay.classList.toggle('hidden', ! isOpen);
    sidebarButton.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
};

sidebarButton?.addEventListener('click', () => {
    setSidebarOpen(sidebar?.classList.contains('-translate-x-full') ?? false);
});

sidebarOverlay?.addEventListener('click', () => setSidebarOpen(false));
