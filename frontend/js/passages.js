/**
 * frontend/js/passages.js
 * -----------------------
 * Source Passages board (3 columns), passage cards, pagination, and review mutations.
 * Enforces: 1 unique passage = 1 review card.
 */

import { api } from './api.js';
import { state, t } from './state.js';
import { renderDocumentOverview, renderHumanVerificationSummary } from './documents.js';

let currentFetchToken = 0;

export async function loadPassagesAndReviews() {
  const fetchToken = ++currentFetchToken;
  const docId = state.selectedDocumentId;
  const cat = state.selectedCategory;
  const { showReviewOnly, includeReviewOnly } = state.filters;

  state.isLoadingPassages = true;

  try {
    // 1. Fetch passages from backend (already grouped by segment_id)
    const passagesRes = await api.get(
      `/api/documents/${docId}/categories/${cat}/passages?show_review_only=${showReviewOnly}&include_review_only=${includeReviewOnly}`
    );
    if (!state.user || fetchToken !== currentFetchToken || state.selectedDocumentId !== docId || state.selectedCategory !== cat) {
      return; // Stale async response discarded or user logged out
    }
    state.passages = passagesRes.passages || [];

    // 2. Fetch existing review decisions from PostgreSQL
    try {
      const reviewsRes = await api.get(`/api/reviews/${docId}`);
      if (!state.user || fetchToken !== currentFetchToken || state.selectedDocumentId !== docId) {
        return; // Stale async response discarded or user logged out
      }
      state.reviews = reviewsRes.reviews || {};
    } catch (err) {
      if (err.name === 'AbortError' || !state.user) return;
      console.warn('Could not load reviews from backend:', err);
      state.reviews = {};
    }
  } catch (err) {
    if (err.name === 'AbortError' || !state.user) return;
    if (fetchToken === currentFetchToken) {
      console.error('Failed to load passages:', err);
      state.passages = [];
    }
  } finally {
    if (fetchToken === currentFetchToken) {
      state.isLoadingPassages = false;
      if (state.user) {
        state.notify();
      }
    }
  }
}

export function groupPassagesByStatus() {
  const grouped = {
    unreviewed: [],
    relevant: [],
    irrelevant: [],
  };

  for (const passage of state.passages) {
    const key = `${state.selectedCategory}::${passage.segment_id}`;
    const storedStatus = state.reviews[key]?.status;

    if (storedStatus === 'relevant') {
      grouped.relevant.push(passage);
    } else if (storedStatus === 'irrelevant') {
      grouped.irrelevant.push(passage);
    } else {
      grouped.unreviewed.push(passage);
    }
  }

  return grouped;
}

export function renderPassagesBoard(container) {
  if (!container) return;

  if (state.isLoadingPassages) {
    container.innerHTML = `
      <div class="card">
        <div class="card-title">
          <span>${t('source_passages')}</span>
          <span class="text-xs text-muted font-mono">${t('loading')}</span>
        </div>
        <div style="padding: var(--space-8); text-align: center; color: var(--text-muted);">
          <span class="spinner" style="margin-bottom: var(--space-2); width: 1.5rem; height: 1.5rem;"></span>
          <div>${t('loading')}</div>
        </div>
      </div>
    `;
    return;
  }

  const grouped = groupPassagesByStatus();
  const reviewCounts = {
    total: state.passages.length,
    reviewed: grouped.relevant.length + grouped.irrelevant.length,
    relevant: grouped.relevant.length,
    irrelevant: grouped.irrelevant.length,
    unreviewed: grouped.unreviewed.length,
  };

  // Update summary headers
  const summaryContainer = document.getElementById('human-verification-container');
  renderHumanVerificationSummary(summaryContainer, reviewCounts);
  const docOverviewContainer = document.getElementById('document-overview-container');
  renderDocumentOverview(docOverviewContainer);

  const columnsConfig = [
    { status: 'unreviewed', title: t('board_unreviewed'), tone: 'badge-neutral', emptyText: t('empty_unreviewed') },
    { status: 'relevant', title: t('board_relevant'), tone: 'badge-success', emptyText: t('empty_relevant') },
    { status: 'irrelevant', title: t('board_irrelevant'), tone: 'badge-danger', emptyText: t('empty_irrelevant') },
  ];

  container.innerHTML = `
    <div class="card">
      <div class="card-title">
        <span>${t('source_passages')}</span>
        <span class="text-xs text-muted font-mono">${reviewCounts.total} ${t('unique_passages_suffix')}</span>
      </div>
      <div class="board-grid">
        ${columnsConfig.map(col => renderColumnHtml(col, grouped[col.status])).join('')}
      </div>
    </div>
  `;

  attachBoardEventListeners(container);
}

function renderColumnHtml(col, passages) {
  const total = passages.length;
  const pageSize = state.pageSize;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  // Clamp current page
  let currentPage = state.pagination[col.status] || 1;
  if (currentPage > totalPages) currentPage = totalPages;
  if (currentPage < 1) currentPage = 1;
  state.pagination[col.status] = currentPage;

  const startIdx = (currentPage - 1) * pageSize;
  const pagePassages = passages.slice(startIdx, startIdx + pageSize);

  let cardsHtml = '';
  if (pagePassages.length === 0) {
    cardsHtml = `<div class="column-empty">${col.emptyText}</div>`;
  } else {
    cardsHtml = pagePassages.map(p => renderPassageCardHtml(p, col.status)).join('');
  }

  const paginationHtml = totalPages > 1 ? `
    <div class="column-footer">
      <button class="pagination-btn" data-action="prev-page" data-status="${col.status}" ${currentPage <= 1 ? 'disabled' : ''}>
        ${t('prev')}
      </button>
      <span class="pagination-page-indicator">${t('page_prefix')} ${currentPage} / ${totalPages}</span>
      <button class="pagination-btn" data-action="next-page" data-status="${col.status}" ${currentPage >= totalPages ? 'disabled' : ''}>
        ${t('next')}
      </button>
    </div>
  ` : '';

  return `
    <div class="board-column">
      <div class="column-header">
        <span class="column-title">
          <span class="badge ${col.tone}">&bull;</span>
          ${col.title}
        </span>
        <span class="column-counter">${total}</span>
      </div>
      <div class="column-cards-container">
        ${cardsHtml}
      </div>
      ${paginationHtml}
    </div>
  `;
}

function renderPassageCardHtml(passage, currentStatus) {
  const passageKey = `${state.selectedCategory}::${passage.segment_id}`;
  const isExpanded = state.activePassageKey === passageKey;
  const isTechOpen = state.technicalOpenKeys.has(passageKey);

  const termBadges = passage.matched_terms.map(t =>
    `<span class="term-tag">${escapeHtml(t.term)} (${t.count})</span>`
  ).join(' ');

  const printedPageBadge = passage.printed_page
    ? `<span class="badge badge-neutral">${t('printed_page')} ${passage.printed_page}</span>`
    : '';

  const requiresReview = passage.matches.some(m => m.requires_review)
    ? `<span class="badge badge-warning">${t('requires_review_badge')}</span>`
    : '';

  // Technical details rows
  let techDetailsHtml = '';
  if (isExpanded) {
    const tableRows = passage.matches.map((m, idx) => `
      <tr>
        <td class="font-mono">#${idx + 1}</td>
        <td class="font-mono">${escapeHtml(m.pattern_id || m.pattern || '—')}</td>
        <td style="font-weight: 600;">${escapeHtml(m.matched_text || m.term || '—')}</td>
        <td class="font-mono">${m.char_start || 0}–${m.char_end || 0}</td>
        <td>${m.requires_review ? t('yes') : t('no')}</td>
        <td>${m.count_in_raw_baseline ? t('yes') : t('no')}</td>
      </tr>
    `).join('');

    techDetailsHtml = `
      <div style="margin-top: 0.5rem; border-top: 1px dashed var(--border-light); padding-top: 0.5rem;">
        <button class="tech-details-toggle" data-action="toggle-tech" data-key="${passageKey}">
          ${isTechOpen ? '▾' : '▸'} ${t('technical_details')} (${passage.matches.length} ${t('matches_count_suffix')})
        </button>
        ${isTechOpen ? `
          <div class="tech-details-table-wrap">
            <table class="tech-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>${t('pattern_label')}</th>
                  <th>${t('matched_term_label')}</th>
                  <th>${t('offsets_label')}</th>
                  <th>${t('req_review_label')}</th>
                  <th>${t('raw_baseline_label')}</th>
                </tr>
              </thead>
              <tbody>
                ${tableRows}
              </tbody>
            </table>
          </div>
        ` : ''}
      </div>
    `;
  }

  const isPending = state.pendingReviewKeys.has(passageKey);

  const actionsHtml = isExpanded ? `
    <div class="passage-actions">
      <button class="btn-outline-success" data-action="review" data-status="relevant" data-key="${passageKey}" ${isPending ? 'disabled' : ''}>
        ${isPending ? '...' : t('mark_relevant')}
      </button>
      <button class="btn-outline-danger" data-action="review" data-status="irrelevant" data-key="${passageKey}" ${isPending ? 'disabled' : ''}>
        ${isPending ? '...' : t('mark_irrelevant')}
      </button>
      <button class="btn-tertiary" data-action="review" data-status="clear" data-key="${passageKey}" ${isPending ? 'disabled' : ''}>
        ${t('clear_decision')}
      </button>
    </div>
  ` : '';

  return `
    <div class="passage-card ${isExpanded ? 'expanded' : ''} ${isPending ? 'opacity-70 pointer-events-none' : ''}" data-key="${passageKey}">
      <div class="passage-card-top">
        <div class="passage-page-meta">
          <span class="badge badge-neutral">${t('pdf_page')} ${passage.pdf_page}</span>
          ${printedPageBadge}
          ${requiresReview}
        </div>
        <button class="btn-tertiary text-xs" data-action="toggle-expand" data-key="${passageKey}" aria-expanded="${isExpanded}">
          ${isExpanded ? t('card_close') : t('card_inspect')}
        </button>
      </div>

      <div class="passage-snippet" data-action="toggle-expand" data-key="${passageKey}">
        ${escapeHtml(passage.text)}
      </div>

      <div class="passage-terms-summary">
        ${termBadges}
      </div>

      ${actionsHtml}
      ${techDetailsHtml}
    </div>
  `;
}

function attachBoardEventListeners(container) {
  if (container._hasBoardListeners) return;
  container._hasBoardListeners = true;

  container.addEventListener('click', async (e) => {
    const target = e.target.closest('button, [data-action]');
    if (!target) return;

    const action = target.getAttribute('data-action');
    const key = target.getAttribute('data-key');
    const status = target.getAttribute('data-status');

    if (action === 'toggle-expand') {
      state.togglePassageExpanded(key);
      renderPassagesBoard(container);
      return;
    }

    if (action === 'toggle-tech') {
      state.toggleTechnicalDetails(key);
      renderPassagesBoard(container);
      return;
    }

    if (action === 'prev-page') {
      const cur = state.pagination[status] || 1;
      if (cur > 1) {
        state.setPagination(status, cur - 1);
        renderPassagesBoard(container);
      }
      return;
    }

    if (action === 'next-page') {
      const cur = state.pagination[status] || 1;
      state.setPagination(status, cur + 1);
      renderPassagesBoard(container);
      return;
    }

    if (action === 'review') {
      e.preventDefault();
      const [cat, segId] = key.split('::');
      await executeReviewDecision(cat, segId, status, container);
    }
  });
}

async function executeReviewDecision(category, segmentId, decision, container) {
  const docId = state.selectedDocumentId;
  const passageKey = `${category}::${segmentId}`;
  const alertEl = document.getElementById('board-alert');

  if (state.pendingReviewKeys.has(passageKey)) {
    return;
  }

  state.pendingReviewKeys.add(passageKey);
  renderPassagesBoard(container);

  try {
    if (decision === 'clear') {
      await api.delete(`/api/reviews/${docId}/${category}/${segmentId}`);
    } else {
      await api.put(`/api/reviews/${docId}/${category}/${segmentId}`, {
        status: decision,
      });
    }

    // Guard against document switch or logout during in-flight network mutation
    if (!state.user || state.selectedDocumentId !== docId) {
      return; // Stale mutation response discarded to prevent cross-document state pollution
    }

    if (state.activePassageKey === passageKey) {
      state.activePassageKey = null;
    }
    state.updateReviewDecision(category, segmentId, decision === 'clear' ? 'unreviewed' : decision);
  } catch (err) {
    if (err.name === 'AbortError' || !state.user) return; // User aborted or session expired
    console.error('Review mutation failed:', err);
    if (alertEl) {
      alertEl.className = 'alert alert-warning';
      alertEl.textContent = err.message || t('rate_limit_warning');
      alertEl.classList.remove('hidden');
      setTimeout(() => alertEl.classList.add('hidden'), 5000);
    }
  } finally {
    state.pendingReviewKeys.delete(passageKey);
    if (state.user && state.selectedDocumentId === docId) {
      renderPassagesBoard(container);
    }
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

