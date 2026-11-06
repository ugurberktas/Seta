/**
 * frontend/js/state.js
 * --------------------
 * Centralized state management and localization dictionary for the application.
 */

export const TRANSLATIONS = {
  tr: {
    app_title: "Security Research Assistant",
    app_subtitle: "Ulusal güvenlik belgelerinde tehdit analizi ve kaynak doğrulama",
    username: "Kullanıcı Adı",
    password: "Şifre",
    sign_in: "Giriş Yap / Sign In",
    sign_out: "Çıkış Yap",
    logged_in_as: "Giriş yapan:",
    language_label: "Dil / Language",
    document_label: "Belge",
    category_label: "Kategori",
    filters_label: "Filtreler",
    show_review_required: "Yalnızca inceleme gerektirenler",
    include_review_only: "Yalnızca inceleme amaçlı eşleşmeleri dahil et",
    analysed_words: "İncelenen Kelimeler",
    total_matches: "Toplam Eşleşme",
    total_segments: "Toplam Segment",
    review_progress: "İnceleme İlerlemesi",
    reviewed_suffix: "incelendi",
    frequency_metric: "1.000 Kelime Başına Sıklık",
    raw_mentions: "Ham Bahsetme Sayısı",
    passage_hits: "Pasaj Eşleşmeleri",
    review_required: "İnceleme Gerekli",
    frequency_help: "Analiz edilen her 1.000 kelimedeki bahsetme sıklığıdır; tehdit şiddetini göstermez.",
    human_verification: "İnsan Doğrulaması",
    reviewed_passages: "İncelenen Pasajlar",
    relevant_passages: "İlgili Pasajlar",
    irrelevant_passages: "İlgisiz Pasajlar",
    unreviewed_passages: "Bekleyen Pasajlar",
    source_passages: "Kaynak Pasajlar",
    board_unreviewed: "Bekleyenler",
    board_relevant: "İlgili",
    board_irrelevant: "İlgisiz",
    empty_unreviewed: "Bekleyen pasaj yok.",
    empty_relevant: "Henüz ilgili olarak işaretlenmiş pasaj yok.",
    empty_irrelevant: "Henüz ilgisiz olarak işaretlenmiş pasaj yok.",
    pdf_page: "PDF Sayfası",
    printed_page: "Basılı Sayfa",
    requires_review_badge: "İnceleme Gerekli",
    technical_details: "Teknik Detaylar",
    mark_relevant: "İlgili",
    mark_irrelevant: "İlgisiz",
    clear_decision: "Temizle",
    cross_doc_title: "Belgeler Arası Karşılaştırma",
    cross_doc_subtitle: "Her değer, ilgili kategorinin analiz edilen 1.000 kelime başına görülme sıklığını gösterir.",
    category_frequency_chart: "Tehdit Kategorisi Sıklığı",
    prev: "< Önceki",
    next: "Sonraki >",
    page_prefix: "Sayfa",
    loading: "Yükleniyor...",
    no_passages_match: "Geçerli filtrelerle eşleşen kaynak pasaj bulunamadı.",
    rate_limit_warning: "Çok fazla işlem yapıldı. Lütfen biraz bekleyin.",
  },
  en: {
    app_title: "Security Research Assistant",
    app_subtitle: "Threat category analysis and source passage verification",
    username: "Username",
    password: "Password",
    sign_in: "Sign In / Giriş Yap",
    sign_out: "Sign Out",
    logged_in_as: "Signed in as:",
    language_label: "Language / Dil",
    document_label: "Document",
    category_label: "Category",
    filters_label: "Filters",
    show_review_required: "Review-required only",
    include_review_only: "Include review-only matches",
    analysed_words: "Analysed Words",
    total_matches: "Total Matches",
    total_segments: "Total Segments",
    review_progress: "Review Progress",
    reviewed_suffix: "reviewed",
    frequency_metric: "Frequency / 1,000 words",
    raw_mentions: "Raw Mentions",
    passage_hits: "Passage Hits",
    review_required: "Review-Required",
    frequency_help: "Mention frequency per 1,000 analysed words; it is not a measure of threat severity.",
    human_verification: "Human Verification",
    reviewed_passages: "Reviewed Passages",
    relevant_passages: "Relevant Passages",
    irrelevant_passages: "Irrelevant Passages",
    unreviewed_passages: "Unreviewed Passages",
    source_passages: "Source Passages",
    board_unreviewed: "Unreviewed",
    board_relevant: "Relevant",
    board_irrelevant: "Irrelevant",
    empty_unreviewed: "No unreviewed passages.",
    empty_relevant: "No passages marked relevant yet.",
    empty_irrelevant: "No passages marked irrelevant yet.",
    pdf_page: "PDF Page",
    printed_page: "Printed Page",
    requires_review_badge: "Requires Review",
    technical_details: "Technical Details",
    mark_relevant: "Relevant",
    mark_irrelevant: "Irrelevant",
    clear_decision: "Clear",
    cross_doc_title: "Cross-Document Comparison",
    cross_doc_subtitle: "Each value shows how often the category appears per 1,000 analysed words.",
    category_frequency_chart: "Threat Category Frequency",
    prev: "< Previous",
    next: "Next >",
    page_prefix: "Page",
    loading: "Loading...",
    no_passages_match: "No source passages match current filters.",
    rate_limit_warning: "Too many requests. Please wait a moment.",
  },
};

export const state = {
  user: null,
  language: 'tr',
  documents: [],
  selectedDocumentId: 'japan_doj_2026',
  currentDocument: null,
  allDocumentsDetail: {},
  selectedCategory: 'Russia',
  passages: [],
  reviews: {},
  filters: {
    showReviewOnly: false,
    includeReviewOnly: false,
  },
  pagination: {
    unreviewed: 1,
    relevant: 1,
    irrelevant: 1,
  },
  pageSize: 15,
  activePassageKey: null, // globally single expanded passage
  technicalOpenKeys: new Set(),
  pendingReviewKeys: new Set(),
  listeners: [],

  subscribe(listener) {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  },

  notify() {
    for (const listener of this.listeners) {
      listener(this);
    }
  },

  setLanguage(lang) {
    if (this.language !== lang && (lang === 'tr' || lang === 'en')) {
      this.language = lang;
      this.notify();
    }
  },

  setUser(user) {
    this.user = user;
    this.notify();
  },

  setDocuments(docs) {
    this.documents = docs;
    this.notify();
  },

  selectDocument(docId) {
    if (this.selectedDocumentId !== docId) {
      this.selectedDocumentId = docId;
      this.activePassageKey = null;
      this.technicalOpenKeys.clear();
      this.pagination = { unreviewed: 1, relevant: 1, irrelevant: 1 };
      this.notify();
    }
  },

  selectCategory(category) {
    if (this.selectedCategory !== category) {
      this.selectedCategory = category;
      this.activePassageKey = null;
      this.technicalOpenKeys.clear();
      this.pagination = { unreviewed: 1, relevant: 1, irrelevant: 1 };
      this.notify();
    }
  },

  setFilters(filters) {
    this.filters = { ...this.filters, ...filters };
    this.activePassageKey = null;
    this.pagination = { unreviewed: 1, relevant: 1, irrelevant: 1 };
    this.notify();
  },

  setPagination(status, page) {
    this.pagination[status] = page;
    this.notify();
  },

  togglePassageExpanded(passageKey) {
    if (this.activePassageKey === passageKey) {
      this.activePassageKey = null;
    } else {
      this.activePassageKey = passageKey;
    }
    this.notify();
  },

  toggleTechnicalDetails(passageKey) {
    if (this.technicalOpenKeys.has(passageKey)) {
      this.technicalOpenKeys.delete(passageKey);
    } else {
      this.technicalOpenKeys.add(passageKey);
    }
    this.notify();
  },

  updateReviewDecision(category, segmentId, status) {
    const key = `${category}::${segmentId}`;
    if (status === 'unreviewed') {
      delete this.reviews[key];
    } else {
      this.reviews[key] = {
        status,
        category,
        segment_id: segmentId,
        updated_at: new Date().toISOString(),
      };
    }
    this.notify();
  },

  resetOnLogout() {
    this.user = null;
    this.currentDocument = null;
    this.passages = [];
    this.reviews = {};
    this.activePassageKey = null;
    this.technicalOpenKeys.clear();
    this.pendingReviewKeys.clear();
    this.pagination = { unreviewed: 1, relevant: 1, irrelevant: 1 };
    this.notify();
  },
};

export function t(key) {
  const dict = TRANSLATIONS[state.language] || TRANSLATIONS.tr;
  return dict[key] || key;
}

