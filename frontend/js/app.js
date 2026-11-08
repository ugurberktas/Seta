/**
 * frontend/js/app.js
 * ------------------
 * Main application coordinator.
 * Manages authentication flow, view switching, event bindings, and UI orchestration.
 */

import { api } from './api.js';
import { state, t } from './state.js';
import { checkAuth, login, logout } from './auth.js';
import {
  loadDocuments,
  loadDocumentDetails,
  loadAllDocumentsForComparison,
  renderDocumentOverview,
  renderCategoryMetrics,
  renderHumanVerificationSummary,
} from './documents.js';
import {
  loadPassagesAndReviews,
  groupPassagesByStatus,
  renderPassagesBoard,
} from './passages.js';
import {
  renderCategoryFrequencyChart,
  renderCrossDocumentChart,
} from './charts.js';

// DOM Elements
let authView;
let appView;
let loginForm;
let loginAlert;
let loginSubmitBtn;
let logoutBtn;
let currentUserName;
let languageSelect;
let langBtnTr;
let langBtnEn;
let langSlider;
let documentSelect;
let documentDropdownTrigger;
let documentDropdownLabel;
let documentDropdownMenu;
let categorySelect;
let categoryDropdownTrigger;
let categoryDropdownLabel;
let categoryDropdownMenu;
let filterReviewOnly;
let filterIncludeBaseline;

// Containers
let documentOverviewContainer;
let categoryMetricsContainer;
let categoryChartContainer;
let humanVerificationContainer;
let sourcePassagesContainer;
let crossDocChartContainer;

document.addEventListener('DOMContentLoaded', async () => {
  initDomReferences();
  bindAuthEvents();
  bindSidebarEvents();

  // Subscribe to central state changes
  state.subscribe(onStateChange);

  // Check existing session
  const user = await checkAuth();
  if (user) {
    showAppView();
    await initAppData();
  } else {
    if (loginAlert) {
      loginAlert.textContent = '';
      loginAlert.classList.add('hidden');
    }
    showAuthView();
  }
});

function initDomReferences() {
  authView = document.getElementById('auth-view');
  appView = document.getElementById('app-view');
  loginForm = document.getElementById('login-form');
  loginAlert = document.getElementById('login-alert');
  loginSubmitBtn = document.getElementById('login-submit-btn');
  logoutBtn = document.getElementById('logout-btn');
  currentUserName = document.getElementById('current-user-name');
  languageSelect = document.getElementById('language-select');
  langBtnTr = document.getElementById('lang-btn-tr');
  langBtnEn = document.getElementById('lang-btn-en');
  langSlider = document.getElementById('lang-slider');
  documentSelect = document.getElementById('document-select');
  documentDropdownTrigger = document.getElementById('document-dropdown-trigger');
  documentDropdownLabel = document.getElementById('document-dropdown-label');
  documentDropdownMenu = document.getElementById('document-dropdown-menu');

  categorySelect = document.getElementById('category-select');
  categoryDropdownTrigger = document.getElementById('category-dropdown-trigger');
  categoryDropdownLabel = document.getElementById('category-dropdown-label');
  categoryDropdownMenu = document.getElementById('category-dropdown-menu');
  filterReviewOnly = document.getElementById('filter-review-only');
  filterIncludeBaseline = document.getElementById('filter-include-baseline');

  documentOverviewContainer = document.getElementById('document-overview-container');
  categoryMetricsContainer = document.getElementById('category-metrics-container');
  categoryChartContainer = document.getElementById('category-chart-container');
  humanVerificationContainer = document.getElementById('human-verification-container');
  sourcePassagesContainer = document.getElementById('source-passages-container');
  crossDocChartContainer = document.getElementById('cross-doc-chart-container');

  // Handle session expiration cleanly by redirecting to login view
  api.setUnauthorizedHandler(() => {
    const wasAuthenticated = Boolean(state.user);
    state.resetOnLogout();
    if (loginForm) loginForm.reset();
    showAuthView();
    if (loginAlert) {
      if (wasAuthenticated) {
        loginAlert.textContent = t('session_expired');
        loginAlert.classList.remove('hidden');
      } else {
        loginAlert.textContent = '';
        loginAlert.classList.add('hidden');
      }
    }
  });
}

function showAuthView() {
  if (authView) authView.classList.remove('hidden');
  if (appView) appView.classList.add('hidden');
}

function showAppView() {
  if (authView) authView.classList.add('hidden');
  if (appView) appView.classList.remove('hidden');
}

function bindAuthEvents() {
  if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      loginAlert.classList.add('hidden');
      loginSubmitBtn.disabled = true;
      loginSubmitBtn.innerHTML = `<span class="spinner"></span> ${t('loading')}`;

      const username = document.getElementById('login-username').value.trim();
      const password = document.getElementById('login-password').value;

      try {
        await login(username, password);
        // Clear password input immediately after successful auth
        const passInput = document.getElementById('login-password');
        if (passInput) passInput.value = '';
        loginAlert.classList.add('hidden');
        showAppView();
        await initAppData();
      } catch (err) {
        let msg = err.message || t('invalid_credentials');
        if (msg.includes('Invalid') || msg.includes('401') || msg.includes('Authentication')) {
          msg = t('invalid_credentials');
        }
        loginAlert.textContent = msg;
        loginAlert.classList.remove('hidden');
      } finally {
        loginSubmitBtn.disabled = false;
        loginSubmitBtn.textContent = t('sign_in');
      }
    });
  }

  if (logoutBtn) {
    logoutBtn.addEventListener('click', async () => {
      await logout();
      if (loginForm) loginForm.reset();
      if (loginAlert) {
        loginAlert.classList.add('hidden');
        loginAlert.textContent = '';
      }
      showAuthView();
    });
  }
}

export async function handleDocumentSelect(docId) {
  if (state.selectedDocumentId === docId && state.currentDocument && !state.isLoadingPassages) {
    return;
  }
  state.selectDocument(docId);
  await Promise.all([
    loadDocumentDetails(docId),
    loadPassagesAndReviews(),
  ]);
}

export async function handleCategorySelect(cat) {
  if (state.selectedCategory === cat && !state.isLoadingPassages) {
    return;
  }
  state.selectCategory(cat);
  await loadPassagesAndReviews();
}

function bindSidebarEvents() {
  if (langBtnTr) {
    langBtnTr.addEventListener('click', () => {
      state.setLanguage('tr');
    });
  }
  if (langBtnEn) {
    langBtnEn.addEventListener('click', () => {
      state.setLanguage('en');
    });
  }

  if (languageSelect) {
    languageSelect.addEventListener('change', (e) => {
      state.setLanguage(e.target.value);
    });
  }

  // Cross-chart interactive selection listeners
  window.addEventListener('sra:select-category', (e) => {
    handleCategorySelect(e.detail);
  });
  window.addEventListener('sra:select-document', (e) => {
    handleDocumentSelect(e.detail);
  });

  if (documentSelect) {
    documentSelect.addEventListener('change', (e) => {
      handleDocumentSelect(e.target.value);
    });
  }

  if (categorySelect) {
    categorySelect.addEventListener('change', (e) => {
      handleCategorySelect(e.target.value);
    });
  }

  setupDropdownEvents();

  if (filterReviewOnly) {
    filterReviewOnly.addEventListener('change', async (e) => {
      state.setFilters({ showReviewOnly: e.target.checked });
      await loadPassagesAndReviews();
    });
  }

  if (filterIncludeBaseline) {
    filterIncludeBaseline.addEventListener('change', async (e) => {
      state.setFilters({ includeReviewOnly: e.target.checked });
      await loadPassagesAndReviews();
    });
  }
}

async function initAppData() {
  try {
    // 1. Load documents list and populate select
    const docs = await loadDocuments();
    populateDocumentSelect(docs);

    // 2. Populate categories
    populateCategorySelect(['Russia', 'China', 'Cyber', 'Hybrid', 'Migration']);

    // 3. Load active document details and passages in parallel
    await Promise.all([
      loadDocumentDetails(state.selectedDocumentId),
      loadPassagesAndReviews(),
    ]);

    // 4. Background preload all documents for comparison chart
    loadAllDocumentsForComparison();
  } catch (err) {
    console.error('Initialization error:', err);
  }
}

function populateDocumentSelect(docs) {
  if (documentSelect) {
    documentSelect.innerHTML = docs.map(doc => {
      const isSelected = doc.id === state.selectedDocumentId ? 'selected' : '';
      return `<option value="${doc.id}" ${isSelected}>${doc.country} (${doc.title})</option>`;
    }).join('');
  }

  if (documentDropdownMenu) {
    documentDropdownMenu.innerHTML = docs.map(doc => {
      const isSelected = doc.id === state.selectedDocumentId;
      return `
        <li class="custom-dropdown-item ${isSelected ? 'selected' : ''}" role="option" aria-selected="${isSelected}" data-value="${doc.id}">
          <div class="dropdown-item-content">
            <span class="dropdown-item-title">${doc.country}</span>
            <span class="dropdown-item-subtitle">${doc.title}</span>
          </div>
          <span class="dropdown-item-check" aria-hidden="true">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
          </span>
        </li>
      `;
    }).join('');
  }
  updateDocumentTriggerLabel();
}

function populateCategorySelect(categories) {
  if (categorySelect) {
    categorySelect.innerHTML = categories.map(cat => {
      const isSelected = cat === state.selectedCategory ? 'selected' : '';
      return `<option value="${cat}" ${isSelected}>${cat}</option>`;
    }).join('');
  }

  if (categoryDropdownMenu) {
    categoryDropdownMenu.innerHTML = categories.map(cat => {
      const isSelected = cat === state.selectedCategory;
      return `
        <li class="custom-dropdown-item ${isSelected ? 'selected' : ''}" role="option" aria-selected="${isSelected}" data-value="${cat}">
          <div class="dropdown-item-content">
            <span class="dropdown-item-title">${cat}</span>
          </div>
          <span class="dropdown-item-check" aria-hidden="true">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
          </span>
        </li>
      `;
    }).join('');
  }
  updateCategoryTriggerLabel();
}

function updateStaticText() {
  // Update document title and static labels by data-i18n attribute
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (key) {
      el.textContent = t(key);
    }
  });

  if (currentUserName && state.user) {
    currentUserName.textContent = state.user.username;
  }
}

function onStateChange() {
  updateStaticText();

  // Sync controls with state
  if (languageSelect && languageSelect.value !== state.language) {
    languageSelect.value = state.language;
  }
  syncLanguageSwitcher(state.language);
  if (documentSelect && documentSelect.value !== state.selectedDocumentId) {
    documentSelect.value = state.selectedDocumentId;
  }
  updateDocumentTriggerLabel();
  syncDropdownSelection(documentDropdownMenu, state.selectedDocumentId);

  if (categorySelect && categorySelect.value !== state.selectedCategory) {
    categorySelect.value = state.selectedCategory;
  }
  updateCategoryTriggerLabel();
  syncDropdownSelection(categoryDropdownMenu, state.selectedCategory);
  if (filterReviewOnly) {
    filterReviewOnly.checked = state.filters.showReviewOnly;
  }
  if (filterIncludeBaseline) {
    filterIncludeBaseline.checked = state.filters.includeReviewOnly;
  }

  // Render main dashboard views
  renderDocumentOverview(documentOverviewContainer);
  renderCategoryMetrics(categoryMetricsContainer);
  renderCategoryFrequencyChart(categoryChartContainer, state.currentDocument, state.language);

  // Review status counts & verification summary
  const grouped = groupPassagesByStatus();
  const total = state.passages.length;
  const reviewCounts = {
    total,
    reviewed: grouped.relevant.length + grouped.irrelevant.length,
    relevant: grouped.relevant.length,
    irrelevant: grouped.irrelevant.length,
    unreviewed: grouped.unreviewed.length,
  };
  renderHumanVerificationSummary(humanVerificationContainer, reviewCounts);

  // Source Passages review board (3-column Kanban)
  renderPassagesBoard(sourcePassagesContainer);

  // Cross-document comparison chart
  renderCrossDocumentChart(crossDocChartContainer, state.allDocumentsDetail, state.selectedCategory, state.language);
}

function syncLanguageSwitcher(lang) {
  if (langBtnTr && langBtnEn && langSlider) {
    if (lang === 'en') {
      langBtnTr.classList.remove('active');
      langBtnTr.setAttribute('aria-checked', 'false');
      langBtnEn.classList.add('active');
      langBtnEn.setAttribute('aria-checked', 'true');
      langSlider.classList.add('slide-en');
    } else {
      langBtnEn.classList.remove('active');
      langBtnEn.setAttribute('aria-checked', 'false');
      langBtnTr.classList.add('active');
      langBtnTr.setAttribute('aria-checked', 'true');
      langSlider.classList.remove('slide-en');
    }
  }
}

function setupDropdownEvents() {
  if (documentDropdownTrigger && documentDropdownMenu) {
    documentDropdownTrigger.addEventListener('click', (e) => {
      e.stopPropagation();
      const isOpen = documentDropdownMenu.classList.contains('open');
      closeAllDropdowns();
      if (!isOpen) {
        documentDropdownMenu.classList.add('open');
        documentDropdownTrigger.classList.add('active');
        documentDropdownTrigger.setAttribute('aria-expanded', 'true');
      }
    });

    documentDropdownMenu.addEventListener('click', (e) => {
      const item = e.target.closest('.custom-dropdown-item');
      if (item && item.dataset.value) {
        const val = item.dataset.value;
        closeAllDropdowns();
        handleDocumentSelect(val);
      }
    });
  }

  if (categoryDropdownTrigger && categoryDropdownMenu) {
    categoryDropdownTrigger.addEventListener('click', (e) => {
      e.stopPropagation();
      const isOpen = categoryDropdownMenu.classList.contains('open');
      closeAllDropdowns();
      if (!isOpen) {
        categoryDropdownMenu.classList.add('open');
        categoryDropdownTrigger.classList.add('active');
        categoryDropdownTrigger.setAttribute('aria-expanded', 'true');
      }
    });

    categoryDropdownMenu.addEventListener('click', (e) => {
      const item = e.target.closest('.custom-dropdown-item');
      if (item && item.dataset.value) {
        const val = item.dataset.value;
        closeAllDropdowns();
        handleCategorySelect(val);
      }
    });
  }

  // Close dropdowns on document click or Escape key
  document.addEventListener('click', () => {
    closeAllDropdowns();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeAllDropdowns();
    }
  });
}

function closeAllDropdowns() {
  if (documentDropdownMenu) {
    documentDropdownMenu.classList.remove('open');
    if (documentDropdownTrigger) {
      documentDropdownTrigger.classList.remove('active');
      documentDropdownTrigger.setAttribute('aria-expanded', 'false');
    }
  }
  if (categoryDropdownMenu) {
    categoryDropdownMenu.classList.remove('open');
    if (categoryDropdownTrigger) {
      categoryDropdownTrigger.classList.remove('active');
      categoryDropdownTrigger.setAttribute('aria-expanded', 'false');
    }
  }
}

function updateDocumentTriggerLabel() {
  if (!documentDropdownLabel) return;
  const currentDoc = (state.documents || []).find(d => d.id === state.selectedDocumentId);
  if (currentDoc) {
    documentDropdownLabel.innerHTML = `<strong>${currentDoc.country}</strong> <span style="opacity: 0.7; font-size: 0.78rem;">(${currentDoc.title})</span>`;
  } else {
    documentDropdownLabel.textContent = state.selectedDocumentId || 'Seçiniz...';
  }
}

function updateCategoryTriggerLabel() {
  if (!categoryDropdownLabel) return;
  categoryDropdownLabel.textContent = state.selectedCategory || 'Russia';
}

function syncDropdownSelection(menuEl, selectedVal) {
  if (!menuEl) return;
  menuEl.querySelectorAll('.custom-dropdown-item').forEach(item => {
    const isSelected = item.dataset.value === selectedVal;
    item.classList.toggle('selected', isSelected);
    item.setAttribute('aria-selected', isSelected ? 'true' : 'false');
  });
}

