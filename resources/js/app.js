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

const autoRefresh = document.querySelector('[data-auto-refresh-url]');

if (autoRefresh) {
    const refreshUrl = autoRefresh.dataset.autoRefreshUrl;
    const refreshAfter = Number.parseInt(autoRefresh.dataset.autoRefreshAfter ?? '8000', 10);

    if (refreshUrl && Number.isFinite(refreshAfter) && refreshAfter > 0) {
        window.setTimeout(() => window.location.replace(refreshUrl), refreshAfter);
    }
}

document.querySelectorAll('[data-password-toggle]').forEach((toggle) => {
    toggle.addEventListener('click', () => {
        const passwordInput = document.querySelector('[data-password-input]');

        if (! (passwordInput instanceof HTMLInputElement)) {
            return;
        }

        const revealsPassword = passwordInput.type === 'password';
        passwordInput.type = revealsPassword ? 'text' : 'password';
        toggle.setAttribute('aria-label', revealsPassword ? 'Ocultar contraseña' : 'Mostrar contraseña');
        toggle.querySelector('[data-password-show-icon]')?.classList.toggle('hidden', revealsPassword);
        toggle.querySelector('[data-password-hide-icon]')?.classList.toggle('hidden', ! revealsPassword);
    });
});

const importType = document.querySelector('[data-import-type]');
const financialEntityField = document.querySelector('[data-financial-entity-field]');
const financialEntity = document.querySelector('[data-financial-entity]');

const updateFinancialEntityVisibility = () => {
    if (! (importType instanceof HTMLSelectElement)
        || ! (financialEntityField instanceof HTMLElement)
        || ! (financialEntity instanceof HTMLSelectElement)) {
        return;
    }

    const isPortfolio = importType.value === 'CARTERA';
    financialEntityField.classList.toggle('hidden', ! isPortfolio);
    financialEntity.required = isPortfolio;

    if (! isPortfolio) {
        financialEntity.value = '';
    }
};

importType?.addEventListener('change', updateFinancialEntityVisibility);
updateFinancialEntityVisibility();
