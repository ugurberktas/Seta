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
let documentSelect;
let categorySelect;
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
  documentSelect = document.getElementById('document-select');
  categorySelect = document.getElementById('category-select');
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
    state.resetOnLogout();
    showAuthView();
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
        showAppView();
        await initAppData();
      } catch (err) {
        loginAlert.textContent = err.message || 'Giriş başarısız.';
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
      showAuthView();
    });
  }
}

function bindSidebarEvents() {
  if (languageSelect) {
    languageSelect.addEventListener('change', (e) => {
      state.setLanguage(e.target.value);
    });
  }

  if (documentSelect) {
    documentSelect.addEventListener('change', async (e) => {
      const docId = e.target.value;
      state.selectDocument(docId);
      await loadDocumentDetails(docId);
      await loadPassagesAndReviews();
    });
  }

  if (categorySelect) {
    categorySelect.addEventListener('change', async (e) => {
      const cat = e.target.value;
      state.selectCategory(cat);
      await loadPassagesAndReviews();
    });
  }

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

    // 3. Load active document details and passages
    await loadDocumentDetails(state.selectedDocumentId);
    await loadPassagesAndReviews();

    // 4. Background preload all documents for comparison chart
    loadAllDocumentsForComparison();
  } catch (err) {
    console.error('Initialization error:', err);
  }
}

function populateDocumentSelect(docs) {
  if (!documentSelect) return;
  documentSelect.innerHTML = docs.map(doc => {
    const isSelected = doc.id === state.selectedDocumentId ? 'selected' : '';
    return `<option value="${doc.id}" ${isSelected}>${doc.country} (${doc.title})</option>`;
  }).join('');
}

function populateCategorySelect(categories) {
  if (!categorySelect) return;
  categorySelect.innerHTML = categories.map(cat => {
    const isSelected = cat === state.selectedCategory ? 'selected' : '';
    return `<option value="${cat}" ${isSelected}>${cat}</option>`;
  }).join('');
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
  if (documentSelect && documentSelect.value !== state.selectedDocumentId) {
    documentSelect.value = state.selectedDocumentId;
  }
  if (categorySelect && categorySelect.value !== state.selectedCategory) {
    categorySelect.value = state.selectedCategory;
  }
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

