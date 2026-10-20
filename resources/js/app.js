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

const searchImportForm = document.querySelector('[data-search-import-form]');
const searchDataset = document.querySelector('[data-search-dataset]');
const searchSource = document.querySelector('[data-search-source]');
const searchSourceNotice = document.querySelector('[data-search-source-notice]');
const searchRefreshMode = document.querySelector('[data-search-refresh-mode]');

const updateSearchRefreshModes = () => {
    if (! (searchSource instanceof HTMLSelectElement)
        || ! (searchRefreshMode instanceof HTMLSelectElement)) {
        return;
    }

    const selectedSource = searchSource.selectedOptions.item(0);
    let availableModes = 0;
    searchRefreshMode.querySelectorAll('option[data-permission]').forEach((option) => {
        const permission = option.dataset.permission;
        const isAvailable = Boolean(
            permission
            && selectedSource?.dataset.dataset
            && selectedSource.dataset[permission] === '1',
        );
        option.hidden = ! isAvailable;
        option.disabled = ! isAvailable;
        availableModes += Number(isAvailable);
    });

    const selectedMode = searchRefreshMode.selectedOptions.item(0);
    if (selectedMode?.dataset.permission && selectedMode.disabled) {
        searchRefreshMode.value = '';
    }
    searchRefreshMode.disabled = availableModes === 0;
};

const updateSearchSources = () => {
    if (! (searchImportForm instanceof HTMLFormElement)
        || ! (searchDataset instanceof HTMLSelectElement)
        || ! (searchSource instanceof HTMLSelectElement)
        || ! (searchSourceNotice instanceof HTMLElement)) {
        return;
    }

    const selectedDataset = searchDataset.value;
    let availableSources = 0;
    searchSource.querySelectorAll('option[data-dataset]').forEach((option) => {
        const isAvailable = option.dataset.dataset === selectedDataset;
        option.hidden = ! isAvailable;
        option.disabled = ! isAvailable;
        availableSources += Number(isAvailable);
    });

    const selectedOption = searchSource.selectedOptions.item(0);
    if (! selectedOption?.dataset.dataset || selectedOption.dataset.dataset !== selectedDataset) {
        searchSource.value = '';
    }

    searchSource.disabled = availableSources === 0;
    searchSourceNotice.classList.toggle('hidden', availableSources > 0);
    updateSearchRefreshModes();
};

searchDataset?.addEventListener('change', updateSearchSources);
searchSource?.addEventListener('change', updateSearchRefreshModes);
updateSearchSources();

const importDeletionDialog = document.querySelector('[data-import-deletion-dialog]');
const importDeletionOpen = document.querySelector('[data-import-deletion-open]');
const importDeletionConfirmation = document.querySelector('[data-import-deletion-confirmation]');
const importDeletionSubmit = document.querySelector('[data-import-deletion-submit]');
let importDeletionTrigger = null;

const updateImportDeletionConfirmation = () => {
    if (importDeletionConfirmation instanceof HTMLInputElement
        && importDeletionSubmit instanceof HTMLButtonElement) {
        importDeletionSubmit.disabled = importDeletionConfirmation.value !== 'ELIMINAR';
    }
};

const closeImportDeletionDialog = () => {
    if (importDeletionDialog instanceof HTMLDialogElement) {
        importDeletionDialog.close();
        document.body.classList.remove('overflow-hidden');

        if (importDeletionTrigger instanceof HTMLElement) {
            importDeletionTrigger.focus();
        }
    }
};

importDeletionOpen?.addEventListener('click', (event) => {
    if (importDeletionDialog instanceof HTMLDialogElement) {
        importDeletionTrigger = event.currentTarget;
        importDeletionDialog.showModal();
        document.body.classList.add('overflow-hidden');
        if (importDeletionConfirmation instanceof HTMLInputElement) {
            importDeletionConfirmation.focus();
        }
    }
});

document.querySelectorAll('[data-import-deletion-close]').forEach((button) => {
    button.addEventListener('click', closeImportDeletionDialog);
});

importDeletionConfirmation?.addEventListener('input', () => {
    updateImportDeletionConfirmation();
});

updateImportDeletionConfirmation();

if (importDeletionDialog instanceof HTMLDialogElement) {
    importDeletionDialog.addEventListener('cancel', () => {
        document.body.classList.remove('overflow-hidden');
    });

    if (importDeletionDialog.hasAttribute('data-import-deletion-auto-open')) {
        importDeletionDialog.showModal();
        document.body.classList.add('overflow-hidden');

        if (importDeletionConfirmation instanceof HTMLInputElement) {
            importDeletionConfirmation.focus();
        }
    }
}
