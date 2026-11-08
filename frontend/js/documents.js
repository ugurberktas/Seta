/**
 * frontend/js/documents.js
 * ------------------------
 * Document metadata, summary metrics, and category metrics rendering.
 */

import { api } from './api.js';
import { state, t } from './state.js';

let currentDocFetchToken = 0;

export async function loadDocuments() {
  const docs = await api.get('/api/documents');
  if (state.user) {
    state.setDocuments(docs);
  }
  return docs;
}

export async function loadDocumentDetails(docId) {
  const fetchToken = ++currentDocFetchToken;
  try {
    const detail = await api.get(`/api/documents/${docId}`);
    if (!state.user || fetchToken !== currentDocFetchToken || state.selectedDocumentId !== docId) {
      return null; // Discard stale response
    }
    state.currentDocument = detail;
    state.allDocumentsDetail[docId] = detail;
    state.notify();
    return detail;
  } catch (err) {
    if (err.name === 'AbortError') return null;
    if (fetchToken === currentDocFetchToken && state.selectedDocumentId === docId && state.user) {
      console.error(`Failed to load document details for ${docId}:`, err);
    }
    return null;
  }
}

export async function loadAllDocumentsForComparison() {
  for (const doc of state.documents) {
    if (!state.user) return;
    if (!state.allDocumentsDetail[doc.id]) {
      try {
        const detail = await api.get(`/api/documents/${doc.id}`);
        if (!state.user) return;
        state.allDocumentsDetail[doc.id] = detail;
      } catch (err) {
        if (err.name === 'AbortError') return;
        console.warn(`Could not preload comparison data for ${doc.id}:`, err);
      }
    }
  }
  if (state.user) {
    state.notify();
  }
}

export function renderDocumentOverview(container) {
  if (!container) return;
  const doc = state.currentDocument;
  if (!doc) {
    container.innerHTML = `
      <div class="card" style="padding: var(--space-6); text-align: center; color: var(--text-muted);">
        <span class="spinner" style="margin-bottom: var(--space-2); width: 1.5rem; height: 1.5rem;"></span>
        <div>${t('loading')}</div>
      </div>
    `;
    return;
  }

  // Calculate review progress across all passages in current document & category
  const totalPassages = state.passages.length;
  let reviewedCount = 0;
  for (const p of state.passages) {
    const key = `${state.selectedCategory}::${p.segment_id}`;
    if (state.reviews[key]?.status === 'relevant' || state.reviews[key]?.status === 'irrelevant') {
      reviewedCount++;
    }
  }

  container.innerHTML = `
    <div class="metrics-grid">
      <div class="metric-card">
        <span class="metric-label">${t('document_label')}</span>
        <span class="metric-value primary" style="font-size: 1.15rem; line-height: 1.3;">${doc.country}</span>
        <span class="metric-caption">${doc.title}</span>
      </div>
      <div class="metric-card">
        <span class="metric-label">${t('analysed_words')}</span>
        <span class="metric-value">${doc.total_words.toLocaleString()}</span>
      </div>
      <div class="metric-card">
        <span class="metric-label">${t('total_matches')}</span>
        <span class="metric-value">${doc.detected_matches.toLocaleString()}</span>
      </div>
      <div class="metric-card">
        <span class="metric-label">${t('total_segments')}</span>
        <span class="metric-value">${doc.total_segments.toLocaleString()}</span>
        <span class="metric-caption">${t('all_segments_caption')}</span>
      </div>
      <div class="metric-card featured">
        <span class="metric-label">${t('review_progress')}</span>
        <span class="metric-value primary">${reviewedCount} / ${totalPassages}</span>
        <span class="metric-caption">${reviewedCount} / ${totalPassages} ${t('reviewed_suffix')}</span>
      </div>
    </div>
  `;
}

export function renderCategoryMetrics(container) {
  if (!container) return;
  const doc = state.currentDocument;
  const cat = state.selectedCategory;
  if (!doc || !doc.categories || !doc.categories[cat]) {
    container.innerHTML = '';
    return;
  }

  const catData = doc.categories[cat];

  container.innerHTML = `
    <div class="category-banner">
      <div class="category-banner-header">
        <h2 class="category-title">${cat}</h2>
        <span class="text-sm text-muted">${doc.title}</span>
      </div>
      <div class="metrics-grid">
        <div class="metric-card featured">
          <span class="metric-label">${t('frequency_metric')}</span>
          <span class="metric-value primary">${Number(catData.frequency_per_1000_words).toFixed(6)}</span>
          <span class="metric-caption">${t('frequency_help')}</span>
        </div>
        <div class="metric-card">
          <span class="metric-label">${t('raw_mentions')}</span>
          <span class="metric-value">${catData.raw_baseline_mentions.toLocaleString()}</span>
          <span class="metric-caption">${t('raw_mentions_caption')}</span>
        </div>
        <div class="metric-card">
          <span class="metric-label">${t('passage_hits')}</span>
          <span class="metric-value">${catData.segment_hits.toLocaleString()}</span>
          <span class="metric-caption">${t('passage_hits_caption')}</span>
        </div>
        <div class="metric-card">
          <span class="metric-label">${t('review_required')}</span>
          <span class="metric-value warning">${catData.review_required_mentions.toLocaleString()}</span>
          <span class="metric-caption">${t('review_required_caption')}</span>
        </div>
      </div>
    </div>
  `;
}

export function renderHumanVerificationSummary(container, reviewCounts) {
  if (!container) return;
  const total = reviewCounts.total || 0;
  const reviewed = reviewCounts.reviewed || 0;
  const relevant = reviewCounts.relevant || 0;
  const irrelevant = reviewCounts.irrelevant || 0;
  const unreviewed = reviewCounts.unreviewed || 0;

  const totalDisplay = state.isLoadingPassages ? '...' : total;
  const reviewedDisplay = state.isLoadingPassages ? '...' : `${reviewed} / ${total}`;
  const relevantDisplay = state.isLoadingPassages ? '...' : relevant;
  const irrelevantDisplay = state.isLoadingPassages ? '...' : irrelevant;
  const unreviewedDisplay = state.isLoadingPassages ? '...' : unreviewed;

  container.innerHTML = `
    <div class="card">
      <h3 class="card-title">${t('human_verification')}</h3>
      <div class="metrics-grid">
        <div class="metric-card featured">
          <span class="metric-label">${t('reviewed_passages')}</span>
          <span class="metric-value primary">${reviewedDisplay}</span>
        </div>
        <div class="metric-card">
          <span class="metric-label">${t('relevant_passages')}</span>
          <span class="metric-value success">${relevantDisplay}</span>
        </div>
        <div class="metric-card">
          <span class="metric-label">${t('irrelevant_passages')}</span>
          <span class="metric-value danger">${irrelevantDisplay}</span>
        </div>
        <div class="metric-card">
          <span class="metric-label">${t('unreviewed_passages')}</span>
          <span class="metric-value neutral">${unreviewedDisplay}</span>
        </div>
      </div>
    </div>
  `;
}

