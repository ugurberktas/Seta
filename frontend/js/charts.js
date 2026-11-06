/**
 * frontend/js/charts.js
 * ---------------------
 * Pure vanilla SVG bar charts for:
 * 1. Category Frequency Comparison (all threat categories in selected document)
 * 2. Cross-Document Comparison (selected category frequency across all 4 documents)
 *
 * Zero external libraries. 100% responsive vector graphics.
 */

import { state, t } from './state.js';

const CANONICAL_CATEGORIES = ['Russia', 'China', 'Cyber', 'Hybrid', 'Migration'];

const CANONICAL_DOCS = [
  { id: 'latvia_sdc_2023', country: 'Latvia', label_tr: 'Letonya', label_en: 'Latvia' },
  { id: 'uk_sdr_2025', country: 'United Kingdom', label_tr: 'Birleşik Krallık', label_en: 'United Kingdom' },
  { id: 'netherlands_dwp_2024', country: 'Netherlands', label_tr: 'Hollanda', label_en: 'Netherlands' },
  { id: 'japan_doj_2026', country: 'Japan', label_tr: 'Japonya', label_en: 'Japan' },
];

/**
 * Render Category Frequency Chart for the selected document.
 * @param {HTMLElement|string} container - Container element or ID
 * @param {object} docDetail - Document detail object from /api/documents/{id}
 * @param {string} lang - 'tr' or 'en'
 */
export function renderCategoryFrequencyChart(container, docDetail, lang = 'tr') {
  const el = typeof container === 'string' ? document.getElementById(container) : container;
  if (!el) return;

  if (!docDetail || !docDetail.categories) {
    el.innerHTML = `<div class="text-muted text-sm" style="padding: 2rem; text-align: center;">${t('loading')}</div>`;
    return;
  }

  // Gather categories data
  const categoriesData = CANONICAL_CATEGORIES.map(cat => {
    const data = docDetail.categories[cat];
    const freq = data ? Number(data.frequency_per_1000_words) || 0 : 0;
    const raw = data ? data.raw_baseline_mentions || 0 : 0;
    return {
      name: cat,
      freq,
      raw,
      isSelected: state.selectedCategory === cat,
    };
  });

  const maxFreq = Math.max(...categoriesData.map(d => d.freq), 0.1);
  const ceiling = Math.ceil(maxFreq * 1.25 * 10) / 10;

  // Chart dimensions
  const width = 640;
  const height = 260;
  const padLeft = 55;
  const padRight = 25;
  const padTop = 30;
  const padBottom = 45;

  const chartW = width - padLeft - padRight;
  const chartH = height - padTop - padBottom;

  // Grid steps (4 horizontal gridlines)
  const steps = 4;
  let gridSvg = '';
  for (let i = 0; i <= steps; i++) {
    const val = (ceiling / steps) * i;
    const y = padTop + chartH - (i / steps) * chartH;
    gridSvg += `
      <line x1="${padLeft}" y1="${y}" x2="${width - padRight}" y2="${y}" stroke="#E2E8F0" stroke-width="1" stroke-dasharray="${i === 0 ? '0' : '3,3'}" />
      <text x="${padLeft - 8}" y="${y + 4}" font-size="10" fill="#64748B" text-anchor="end" font-family="sans-serif">${val.toFixed(2)}</text>
    `;
  }

  // Bars
  const numBars = categoriesData.length;
  const slotW = chartW / numBars;
  const barW = Math.min(60, slotW * 0.6);

  let barsSvg = '';
  categoriesData.forEach((item, idx) => {
    const barH = ceiling > 0 ? (item.freq / ceiling) * chartH : 0;
    const x = padLeft + idx * slotW + (slotW - barW) / 2;
    const y = padTop + chartH - barH;

    const fill = item.isSelected ? '#2563EB' : '#93C5FD';
    const hoverClass = 'chart-interactive-bar';

    barsSvg += `
      <g class="${hoverClass}" data-category="${item.name}" style="cursor: pointer;">
        <rect x="${x}" y="${y}" width="${barW}" height="${barH}" rx="4" fill="${fill}" />
        <text x="${x + barW / 2}" y="${y - 6}" font-size="11" font-weight="600" fill="${item.isSelected ? '#1D4ED8' : '#334155'}" text-anchor="middle" font-family="sans-serif">
          ${item.freq.toFixed(3)}
        </text>
        <text x="${x + barW / 2}" y="${padTop + chartH + 18}" font-size="11" font-weight="${item.isSelected ? '700' : '500'}" fill="${item.isSelected ? '#0F172A' : '#475569'}" text-anchor="middle" font-family="sans-serif">
          ${item.name}
        </text>
        <title>${item.name}: ${item.freq.toFixed(3)} / 1,000 words (${item.raw} mentions)</title>
      </g>
    `;
  });

  el.innerHTML = `
    <div class="card" style="margin-bottom: var(--space-6);">
      <div class="card-header" style="display: flex; justify-content: space-between; align-items: baseline;">
        <h3 class="card-title">${t('category_frequency_chart')}</h3>
        <span class="text-xs text-muted">${t('frequency_help')}</span>
      </div>
      <div class="chart-box">
        <svg class="chart-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="${t('category_frequency_chart')}">
          ${gridSvg}
          ${barsSvg}
        </svg>
      </div>
    </div>
  `;

  // Attach interactive click on bars to switch active category
  el.querySelectorAll('.chart-interactive-bar').forEach(group => {
    group.addEventListener('click', () => {
      const cat = group.getAttribute('data-category');
      if (cat && cat !== state.selectedCategory) {
        state.selectCategory(cat);
      }
    });
  });
}

/**
 * Render Cross-Document Comparison Chart for the selected threat category.
 * @param {HTMLElement|string} container - Container element or ID
 * @param {object} allDocsMap - Map of docId -> docDetail
 * @param {string} category - Selected category e.g. 'Russia'
 * @param {string} lang - 'tr' or 'en'
 */
export function renderCrossDocumentChart(container, allDocsMap, category, lang = 'tr') {
  const el = typeof container === 'string' ? document.getElementById(container) : container;
  if (!el) return;

  if (!allDocsMap || Object.keys(allDocsMap).length === 0) {
    el.innerHTML = `<div class="text-muted text-sm" style="padding: 2rem; text-align: center;">${t('loading')}</div>`;
    return;
  }

  // Gather documents comparison data
  const comparisonData = CANONICAL_DOCS.map(doc => {
    const detail = allDocsMap[doc.id];
    const catData = detail?.categories?.[category];
    const freq = catData ? Number(catData.frequency_per_1000_words) || 0 : 0;
    const raw = catData ? catData.raw_baseline_mentions || 0 : 0;
    const countryLabel = lang === 'tr' ? doc.label_tr : doc.label_en;

    return {
      docId: doc.id,
      country: countryLabel,
      freq,
      raw,
      isSelected: state.selectedDocumentId === doc.id,
    };
  });

  const maxFreq = Math.max(...comparisonData.map(d => d.freq), 0.1);
  const ceiling = Math.ceil(maxFreq * 1.25 * 10) / 10;

  // Chart dimensions
  const width = 640;
  const height = 260;
  const padLeft = 55;
  const padRight = 25;
  const padTop = 30;
  const padBottom = 45;

  const chartW = width - padLeft - padRight;
  const chartH = height - padTop - padBottom;

  // Grid steps (4 horizontal gridlines)
  const steps = 4;
  let gridSvg = '';
  for (let i = 0; i <= steps; i++) {
    const val = (ceiling / steps) * i;
    const y = padTop + chartH - (i / steps) * chartH;
    gridSvg += `
      <line x1="${padLeft}" y1="${y}" x2="${width - padRight}" y2="${y}" stroke="#E2E8F0" stroke-width="1" stroke-dasharray="${i === 0 ? '0' : '3,3'}" />
      <text x="${padLeft - 8}" y="${y + 4}" font-size="10" fill="#64748B" text-anchor="end" font-family="sans-serif">${val.toFixed(2)}</text>
    `;
  }

  // Bars
  const numBars = comparisonData.length;
  const slotW = chartW / numBars;
  const barW = Math.min(68, slotW * 0.6);

  let barsSvg = '';
  comparisonData.forEach((item, idx) => {
    const barH = ceiling > 0 ? (item.freq / ceiling) * chartH : 0;
    const x = padLeft + idx * slotW + (slotW - barW) / 2;
    const y = padTop + chartH - barH;

    const fill = item.isSelected ? '#2563EB' : '#93C5FD';
    const hoverClass = 'chart-interactive-doc-bar';

    barsSvg += `
      <g class="${hoverClass}" data-docid="${item.docId}" style="cursor: pointer;">
        <rect x="${x}" y="${y}" width="${barW}" height="${barH}" rx="4" fill="${fill}" />
        <text x="${x + barW / 2}" y="${y - 6}" font-size="11" font-weight="600" fill="${item.isSelected ? '#1D4ED8' : '#334155'}" text-anchor="middle" font-family="sans-serif">
          ${item.freq.toFixed(3)}
        </text>
        <text x="${x + barW / 2}" y="${padTop + chartH + 18}" font-size="11" font-weight="${item.isSelected ? '700' : '500'}" fill="${item.isSelected ? '#0F172A' : '#475569'}" text-anchor="middle" font-family="sans-serif">
          ${item.country}
        </text>
        <title>${item.country} - ${category}: ${item.freq.toFixed(3)} / 1,000 words (${item.raw} mentions)</title>
      </g>
    `;
  });

  el.innerHTML = `
    <div class="card" style="margin-top: var(--space-6);">
      <div class="card-header" style="display: flex; justify-content: space-between; align-items: baseline;">
        <h3 class="card-title">${t('cross_doc_title')} (${category})</h3>
        <span class="text-xs text-muted">${t('cross_doc_subtitle')}</span>
      </div>
      <div class="chart-box">
        <svg class="chart-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="${t('cross_doc_title')}">
          ${gridSvg}
          ${barsSvg}
        </svg>
      </div>
    </div>
  `;

  // Attach interactive click on bars to switch active document
  el.querySelectorAll('.chart-interactive-doc-bar').forEach(group => {
    group.addEventListener('click', () => {
      const docId = group.getAttribute('data-docid');
      if (docId && docId !== state.selectedDocumentId) {
        state.selectDocument(docId);
      }
    });
  });
}

