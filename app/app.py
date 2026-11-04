"""
app/app.py
----------
Security Research Assistant — Streamlit UI v2 (Overview + Source Passages + VERIFY)

Run from repo root:
    .venv/bin/streamlit run app/app.py
"""

from __future__ import annotations

from collections import Counter, OrderedDict
from html import escape
import json
from pathlib import Path
import sys
from typing import Any

import streamlit as st

# ---------------------------------------------------------------------------
# Import review_store from src/ using PROJECT_ROOT
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from review_store import (  # noqa: E402
    get_review_status,
    set_review_status,
    clear_review,
    get_review_summary,
    load_reviews,
    get_passage_review_status,
    set_passage_review_status,
    clear_passage_review,
    resolve_passage_status,
    make_passage_key,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

# ---------------------------------------------------------------------------
# Document and UI config
# ---------------------------------------------------------------------------

DOCUMENTS: dict[str, str] = {
    "latvia_sdc_2023": "State Defence Concept 2023–2027",
    "uk_sdr_2025": "Strategic Defence Review 2025",
    "netherlands_dwp_2024": "Defence White Paper 2024",
    "japan_doj_2026": "Defense of Japan 2026",
}

COUNTRY_LABELS: dict[str, dict[str, str]] = {
    "latvia_sdc_2023": {"tr": "Letonya", "en": "Latvia"},
    "uk_sdr_2025": {"tr": "Birleşik Krallık", "en": "United Kingdom"},
    "netherlands_dwp_2024": {"tr": "Hollanda", "en": "Netherlands"},
    "japan_doj_2026": {"tr": "Japonya", "en": "Japan"},
}

CATEGORY_LABELS: dict[str, dict[str, str]] = {
    "Russia": {"tr": "Rusya", "en": "Russia"},
    "Cyber": {"tr": "Siber", "en": "Cyber"},
    "Hybrid": {"tr": "Hibrit", "en": "Hybrid"},
    "China": {"tr": "Çin", "en": "China"},
    "Migration": {"tr": "Göç", "en": "Migration"},
}

UI_TEXT: dict[str, dict[str, str]] = {
    "tr": {
        "eyebrow": "Araştırma aracı",
        "title": "Güvenlik Araştırma Asistanı",
        "description": "Ulusal güvenlik ve savunma belgelerinde tehdit kategorilerini karşılaştırın ve kaynak pasajları doğrulayın.",
        "methodology": "Bu PoC, kompakt bir İngilizce sözlük kullanır ve SETA'nın özgün çok dilli sözlüğünü birebir yeniden üretmez.",
        "filters": "Filtreler",
        "document": "Belge",
        "category": "Kategori",
        "document_overview": "Belge Özeti",
        "country": "Ülke",
        "analysed_words": "İncelenen kelimeler",
        "total_matches": "Toplam eşleşme",
        "total_segments": "Toplam segment",
        "source_passages": "Kaynak Pasajlar",
        "review_progress": "İnceleme ilerlemesi",
        "reviewed_suffix": "incelendi",
        "category_heading": "Kategori",
        "threat_category_frequency": "Tehdit Kategorisi Sıklığı",
        "frequency": "1.000 kelime başına sıklık",
        "raw_mentions": "Ham bahsetme sayısı",
        "segment_hits": "Pasaj eşleşmeleri",
        "review_required": "İnceleme gerekli",
        "frequency_help": "Bu değer, analiz edilen her 1.000 kelimedeki bahsetme sıklığıdır; tehdit şiddetini göstermez.",
        "review_required_help": "Bu eşleşmeler bağlamın insan tarafından kontrol edilmesini gerektirir.",
        "human_verification": "İnsan Doğrulaması",
        "reviewed": "İncelendi",
        "relevant": "İlgili",
        "irrelevant": "İlgisiz",
        "unreviewed": "İncelenmedi",
        "reviewed_passages": "İncelenen Pasajlar",
        "relevant_passages": "İlgili Pasajlar",
        "irrelevant_passages": "İlgisiz Pasajlar",
        "unreviewed_passages": "Bekleyen Pasajlar",
        "passage_summary_help": "Bu kategori, {passages} kaynak pasaj genelinde {mentions} terim bahsetmesi içermektedir.",
        "matched_terms": "Eşleşen terimler",
        "offsets": "Karakter aralığı",
        "legacy_conflict_badge": "Eski çelişki",
        "show_review_required": "Yalnızca inceleme gerektiren eşleşmeleri göster",
        "include_review_only": "Yalnızca inceleme amaçlı eşleşmeleri dahil et",
        "review_status": "İnceleme durumu",
        "advanced_filters": "Gelişmiş filtreler",
        "additional_review_filter": "İnceleme durumu",
        "all": "Tümü",
        "no_passages": "Geçerli filtrelerle eşleşen kaynak pasaj bulunamadı.",
        "review_board_unreviewed": "Bekleyenler",
        "review_board_relevant": "İlgili",
        "review_board_irrelevant": "İlgisiz",
        "passage_count": "pasaj",
        "empty_unreviewed": "Bekleyen pasaj yok.",
        "empty_relevant": "Henüz ilgili olarak işaretlenmiş pasaj yok.",
        "empty_irrelevant": "Henüz ilgisiz olarak işaretlenmiş pasaj yok.",
        "source_information": "Kaynak bilgisi",
        "requires_review": "İnceleme gerekli",
        "in_raw_baseline": "Ham taban sayımında",
        "status": "Durum",
        "segment_text": "Pasaj metni",
        "matched_term": "Eşleşen terim",
        "clear": "Temizle",
        "technical_details": "Teknik detaylar",
        "pdf_page": "PDF sayfası",
        "printed_page": "Basılı sayfa",
        "cross_document_comparison": "Belgeler Arası Karşılaştırma",
        "comparison_subtitle": "Her değer, ilgili kategorinin analiz edilen 1.000 kelime başına görülme sıklığını gösterir.",
        "comparison_unavailable": "Karşılaştırma için en az iki belgenin analiz edilmiş olması gerekir.",
        "comparison_methodology": "Sonuçlar kompakt bir İngilizce sözlüğe dayanır ve kaynak raporun özgün çok dilli analizinden farklı olabilir.",
        "analysis_missing": "Bu belge için analiz çıktısı bulunamadı.",
        "error_setting_review": "İnceleme durumu ayarlanamadı",
        "error_clearing_review": "İnceleme durumu temizlenemedi",
        "page_prefix": "Sayfa",
        "prev_page": "< Önceki",
        "next_page": "Sonraki >",
    },
    "en": {
        "eyebrow": "Research tool",
        "title": "Security Research Assistant",
        "description": "Compare threat categories across national security and defence documents, and verify the source passages.",
        "methodology": "This PoC uses a compact English dictionary and does not reproduce SETA's original multilingual dictionary.",
        "filters": "Filters",
        "document": "Document",
        "category": "Category",
        "document_overview": "Document Overview",
        "country": "Country",
        "analysed_words": "Analysed words",
        "total_matches": "Total matches",
        "total_segments": "Total segments",
        "source_passages": "Source Passages",
        "review_progress": "Review progress",
        "reviewed_suffix": "reviewed",
        "category_heading": "Category",
        "threat_category_frequency": "Threat Category Frequency",
        "frequency": "Frequency / 1,000 words",
        "raw_mentions": "Raw mentions",
        "segment_hits": "Passage hits",
        "review_required": "Review-required",
        "frequency_help": "This is mention frequency per 1,000 analysed words; it is not a measure of threat severity.",
        "review_required_help": "These matches require human review of their context.",
        "human_verification": "Human Verification",
        "reviewed": "Reviewed",
        "relevant": "Relevant",
        "irrelevant": "Irrelevant",
        "unreviewed": "Unreviewed",
        "reviewed_passages": "Reviewed Passages",
        "relevant_passages": "Relevant Passages",
        "irrelevant_passages": "Irrelevant Passages",
        "unreviewed_passages": "Unreviewed Passages",
        "passage_summary_help": "This category contains {mentions} term mentions across {passages} source passages.",
        "matched_terms": "Matched terms",
        "offsets": "Offsets",
        "legacy_conflict_badge": "Legacy conflict",
        "show_review_required": "Show review-required matches only",
        "include_review_only": "Include review-only matches",
        "review_status": "Review status",
        "advanced_filters": "Advanced filters",
        "additional_review_filter": "Review status",
        "all": "All",
        "no_passages": "No source passages match the current filters.",
        "review_board_unreviewed": "Unreviewed",
        "review_board_relevant": "Relevant",
        "review_board_irrelevant": "Irrelevant",
        "passage_count": "passages",
        "empty_unreviewed": "No unreviewed passages.",
        "empty_relevant": "No passages marked relevant yet.",
        "empty_irrelevant": "No passages marked irrelevant yet.",
        "source_information": "Source information",
        "requires_review": "Requires review",
        "in_raw_baseline": "In raw baseline",
        "status": "Status",
        "segment_text": "Segment text",
        "matched_term": "Matched term",
        "clear": "Clear",
        "technical_details": "Technical details",
        "pdf_page": "PDF page",
        "printed_page": "Printed page",
        "cross_document_comparison": "Cross-document comparison",
        "comparison_subtitle": "Each value shows how often the category appears per 1,000 analysed words.",
        "comparison_unavailable": "At least two documents must be analysed to show a comparison.",
        "comparison_methodology": "Results use a compact English dictionary and may differ from the source report's original multilingual analysis.",
        "analysis_missing": "Analysis output not found for this document.",
        "error_setting_review": "Error setting review",
        "error_clearing_review": "Error clearing review",
        "page_prefix": "Page",
        "prev_page": "< Previous",
        "next_page": "Next >",
    },
}

SCOPE = "core_body"
PAGE_SIZE = 15

# ---------------------------------------------------------------------------
# Data loading  (analysis JSON is stable — cache it; reviews are live — never cache)
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def load_analysis(document_id: str) -> dict[str, Any] | None:
    """Load threat-match JSON. Returns None if the file is missing."""
    path = PROCESSED_DIR / f"{document_id}_{SCOPE}_threat_matches.json"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ordered_categories(data: dict) -> list[str]:
    ranking = data.get("ranking_by_frequency")
    if ranking and isinstance(ranking, list):
        return [r["category"] for r in ranking]
    return list(data.get("summary", {}).keys())


def fmt_freq(value: float) -> str:
    return f"{value:.3f}"


def document_label(document_id: str, language: str) -> str:
    country = COUNTRY_LABELS.get(document_id, {}).get(language, document_id)
    title = DOCUMENTS.get(document_id, document_id)
    return f"{country} — {title}"


def category_label(category: str, language: str) -> str:
    return CATEGORY_LABELS.get(category, {}).get(language, category)


def status_label(status: str, text: dict[str, str]) -> str:
    return {
        "relevant": text["relevant"],
        "irrelevant": text["irrelevant"],
    }.get(status, text["unreviewed"])


def get_active_matches(
    data: dict,
    category: str,
    show_review_only: bool = False,
    include_review_only: bool = False,
) -> list[dict]:
    """Filter category matches respecting strict filter order.

    Order:
    1. Filter out review-only matches unless explicitly included.
    2. Filter to review-required only if requested.
    """
    matches = [m for m in data.get("matches", []) if m["category"] == category]
    if not include_review_only:
        matches = [m for m in matches if m.get("count_in_raw_baseline", True)]
    if show_review_only:
        matches = [m for m in matches if m.get("requires_review", False)]
    return matches


def group_matches_into_passages(
    matches: list[dict],
    category: str,
) -> list[dict]:
    """Group active matches into unique passage items keyed by (category, segment_id).

    Preserves original document order.
    """
    passages_by_id: dict[str, dict] = OrderedDict()
    for m in matches:
        seg_id = m["segment_id"]
        if seg_id not in passages_by_id:
            passages_by_id[seg_id] = {
                "segment_id": seg_id,
                "category": category,
                "passage_key": make_passage_key(category, seg_id),
                "page_number_pdf": m.get("page_number_pdf"),
                "page_number_printed": m.get("page_number_printed"),
                "segment_text": m.get("segment_text", ""),
                "matches": [],
            }
        passages_by_id[seg_id]["matches"].append(m)

    result = []
    for p in passages_by_id.values():
        counts = Counter(m.get("matched_text") for m in p["matches"])
        p["term_counts"] = dict(counts)
        result.append(p)
    return result


def group_passages_by_status(
    document_id: str,
    category: str,
    passages: list[dict],
    review_store_data: dict,
    review_status_filter: str = "all",
) -> tuple[dict[str, list[dict]], dict[str, int]]:
    """Group active passages by review status using a loaded review store snapshot."""
    valid_statuses = ("unreviewed", "relevant", "irrelevant")
    grouped: dict[str, list[dict]] = {status: [] for status in valid_statuses}
    reviews_dict = review_store_data.get("reviews", {})

    for p in passages:
        status, diag = resolve_passage_status(
            category=category,
            segment_id=p["segment_id"],
            constituent_matches=p["matches"],
            reviews_dict=reviews_dict,
        )
        p["review_status"] = status
        p["review_diagnostics"] = diag

        if review_status_filter == "all" or status == review_status_filter:
            grouped[status].append(p)

    counts = {
        "unreviewed": len(grouped["unreviewed"]),
        "relevant": len(grouped["relevant"]),
        "irrelevant": len(grouped["irrelevant"]),
        "reviewed": len(grouped["relevant"]) + len(grouped["irrelevant"]),
        "total": sum(len(items) for items in grouped.values()),
    }
    return grouped, counts


def group_matches_by_status(
    doc_id: str,
    matches: list[dict],
    review_status_filter: str = "all",
) -> tuple[dict[str, list[dict]], dict[str, int]]:
    """Legacy helper: group active matches by review status."""
    valid_statuses = ("unreviewed", "relevant", "irrelevant")
    grouped: dict[str, list[dict]] = {status: [] for status in valid_statuses}

    for match in matches:
        current_status = get_review_status(doc_id, match["match_id"])
        if current_status not in valid_statuses:
            current_status = "unreviewed"
        if review_status_filter == "all" or current_status == review_status_filter:
            grouped[current_status].append(match)

    counts = {
        "unreviewed": len(grouped["unreviewed"]),
        "relevant": len(grouped["relevant"]),
        "irrelevant": len(grouped["irrelevant"]),
        "reviewed": len(grouped["relevant"]) + len(grouped["irrelevant"]),
        "total": sum(len(items) for items in grouped.values()),
    }
    return grouped, counts


def escape_markdown_label(value: Any) -> str:
    """Keep dynamic text literal inside Streamlit widget labels."""
    escaped = str(value).replace("\\", "\\\\")
    for character in ("`", "*", "_", "[", "]"):
        escaped = escaped.replace(character, f"\\{character}")
    return escaped


def passage_preview(value: Any, limit: int = 126) -> str:
    """Return a compact display-only preview without changing source data."""
    compact = " ".join(str(value).split())
    if len(compact) <= limit:
        return compact
    shortened = compact[:limit].rsplit(" ", 1)[0]
    return f"{shortened or compact[:limit]}…"


def toggle_active_passage(match_id: str) -> None:
    """Keep exactly one review-board passage active across all columns."""
    active_id = st.session_state.get("active_passage_id")
    st.session_state["active_passage_id"] = (
        None if active_id == match_id else match_id
    )


def apply_ui_styles() -> None:
    """Apply a small, presentation-only theme on top of Streamlit defaults."""
    st.markdown(
        """
        <style>
        :root {
            --research-bg: #F6F8FC;
            --research-card: #FFFFFF;
            --research-border: #DDE5EE;
            --research-text: #24354B;
            --research-muted: #6B7A90;
            --research-navy: #1F3556;
            --research-blue: #3B73B9;
            --research-soft-blue: #EAF2FC;
            --research-soft-green: #EAF7F0;
            --research-soft-amber: #FFF6E5;
            --research-soft-red: #FDEEEE;
        }

        html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"] {
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display",
                "SF Pro Text", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }
        [data-testid="stAppViewContainer"] {
            background: var(--research-bg);
            color: var(--research-text);
        }
        [data-testid="stHeader"] { background: rgba(246, 248, 252, 0.92); }
        [data-testid="stSidebar"] {
            background: #FFFFFF;
            border-right: 1px solid var(--research-border);
        }
        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 0.8rem; }
        [data-testid="stMainBlockContainer"] {
            max-width: 1240px;
            padding-top: 2rem;
            padding-bottom: 4.5rem;
        }
        h1, h2, h3, h4, h5, h6 {
            color: var(--research-navy) !important;
            letter-spacing: -0.02em;
        }
        h1 { font-size: clamp(2.1rem, 3.2vw, 2.5rem) !important; font-weight: 720 !important; }
        h2, h3 { font-size: clamp(1.45rem, 2.2vw, 1.7rem) !important; font-weight: 680 !important; margin-top: 0.1rem !important; }
        p, label, [data-testid="stCaptionContainer"] { color: var(--research-text) !important; }
        [data-testid="stCaptionContainer"] {
            color: var(--research-muted) !important;
            font-size: 0.88rem;
            line-height: 1.5;
        }
        hr { border-color: var(--research-border) !important; margin: 1.15rem 0 !important; }

        .hero-panel {
            padding: 1.65rem 1.8rem 1.55rem;
            margin-bottom: 2rem;
            background: linear-gradient(120deg, #FFFFFF 0%, #F0F5FC 100%);
            border: 1px solid #D8E4F1;
            border-radius: 14px;
            box-shadow: 0 8px 24px rgba(31, 53, 86, 0.045);
        }
        .hero-eyebrow, .sidebar-section-label {
            color: var(--research-blue);
            font-size: 0.72rem;
            font-weight: 750;
            letter-spacing: 0.1em;
            text-transform: uppercase;
        }
        .hero-title {
            color: var(--research-navy);
            font-size: clamp(2.1rem, 3.2vw, 2.5rem);
            font-weight: 730;
            letter-spacing: -0.035em;
            line-height: 1.12;
            margin: 0.35rem 0 0.55rem;
        }
        .hero-description {
            color: var(--research-text);
            font-size: 1rem;
            line-height: 1.6;
            margin: 0;
            max-width: 780px;
        }
        .hero-methodology {
            color: var(--research-muted);
            font-size: 0.85rem;
            line-height: 1.5;
            margin: 0.55rem 0 0;
        }
        .sidebar-section-label { margin: 0.2rem 0 0.05rem; }

        [data-baseweb="select"] > div {
            background: #FFFFFF !important;
            border-color: #DCE3EA !important;
        }
        [data-baseweb="select"] span,
        [data-baseweb="select"] input { color: var(--research-text) !important; }
        .react-aria-ComboBox [role="group"] {
            background: #FFFFFF !important;
            border-color: #DCE3EA !important;
        }
        .react-aria-ComboBox input,
        .react-aria-ComboBox button {
            color: var(--research-text) !important;
            background: transparent !important;
        }

        /* -----------------------------------------------------------------
           Sidebar layout, dropdowns, checkboxes and expander
           ----------------------------------------------------------------- */
        [data-testid="stSidebar"] {
            background-color: #F8FAFD;
            border-right: 1px solid #DCE5EF;
        }
        .sidebar-section-label {
            color: var(--research-blue);
            font-size: 0.72rem;
            font-weight: 750;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin: 0.15rem 0 0.25rem;
        }
        [data-testid="stSidebar"] [data-testid="stSelectbox"] + [data-testid="stElementContainer"] .sidebar-section-label {
            margin-top: 0.7rem;
        }
        [data-testid="stSidebar"] hr {
            margin: 0.95rem 0 0.85rem !important;
            border: 0 !important;
            border-top: 1px solid #E2E8F0 !important;
        }

        /* Sidebar Selectbox */
        [data-testid="stSidebar"] [data-testid="stSelectbox"] {
            margin-bottom: 0.25rem;
        }
        [data-testid="stSidebar"] .react-aria-ComboBox [role="group"] {
            background: #FFFFFF !important;
            border: 1px solid #DCE5EF !important;
            border-radius: 8px !important;
            box-shadow: 0 1px 2px rgba(31, 53, 86, 0.03) !important;
            transition: border-color 0.15s ease, box-shadow 0.15s ease;
        }
        [data-testid="stSidebar"] .react-aria-ComboBox [role="group"]:hover {
            border-color: #B8CADA !important;
            box-shadow: 0 2px 6px rgba(31, 53, 86, 0.06) !important;
        }
        [data-testid="stSidebar"] .react-aria-ComboBox [role="group"]:focus-within {
            border-color: var(--research-blue) !important;
            box-shadow: 0 0 0 2px rgba(27, 100, 218, 0.12) !important;
        }
        [data-testid="stSidebar"] .react-aria-ComboBox input {
            color: var(--research-navy) !important;
            font-size: 0.86rem !important;
            font-weight: 550 !important;
            text-overflow: ellipsis !important;
            overflow: hidden !important;
            white-space: nowrap !important;
        }
        [data-testid="stSidebar"] .react-aria-ComboBox button {
            color: #64748B !important;
        }

        /* Selectbox Virtual Dropdown popover (Light Theme) */
        [data-testid="stSelectboxVirtualDropdown"] {
            background-color: #FFFFFF !important;
            border: 1px solid #DCE5EF !important;
            border-radius: 9px !important;
            box-shadow: 0 8px 24px rgba(31, 53, 86, 0.12) !important;
            padding: 0.3rem !important;
        }
        [data-testid="stSelectboxVirtualDropdown"] [role="listbox"] {
            background-color: #FFFFFF !important;
        }
        [data-testid="stSelectboxVirtualDropdown"] [role="option"] {
            color: var(--research-navy) !important;
            font-size: 0.86rem !important;
            padding: 0.45rem 0.75rem !important;
            border-radius: 6px !important;
            background-color: transparent !important;
            cursor: pointer !important;
            transition: background-color 0.12s ease;
        }
        [data-testid="stSelectboxVirtualDropdown"] [role="option"][data-focused="true"],
        [data-testid="stSelectboxVirtualDropdown"] [role="option"]:hover {
            background-color: #F1F6FB !important;
            color: var(--research-blue) !important;
        }
        [data-testid="stSelectboxVirtualDropdown"] [role="option"][aria-selected="true"],
        [data-testid="stSelectboxVirtualDropdown"] [role="option"][data-selected="true"] {
            background-color: #E8F1FA !important;
            color: var(--research-blue) !important;
            font-weight: 650 !important;
        }
        [data-testid="stSelectboxVirtualDropdown"] [role="option"] div[data-item-hl] {
            color: inherit !important;
        }

        /* Sidebar Checkboxes: clean, light, blue/navy design language */
        [data-testid="stSidebar"] [data-testid="stCheckbox"] {
            margin-bottom: 0.45rem;
        }
        [data-testid="stSidebar"] [data-testid="stCheckbox"] label {
            align-items: flex-start !important;
            cursor: pointer !important;
            gap: 0.55rem !important;
        }
        [data-testid="stSidebar"] [data-testid="stCheckbox"] label > div:first-of-type {
            background-color: #FFFFFF !important;
            border: 1.5px solid #CAD6E2 !important;
            border-radius: 4px !important;
            margin-top: 0.15rem !important;
            transition: all 0.15s ease;
        }
        [data-testid="stSidebar"] [data-testid="stCheckbox"] label:hover > div:first-of-type {
            border-color: var(--research-blue) !important;
            background-color: #F0F6FD !important;
        }
        [data-testid="stSidebar"] [data-testid="stCheckbox"] label[data-selected="true"] > div:first-of-type,
        [data-testid="stSidebar"] [data-testid="stCheckbox"] label:has(input:checked) > div:first-of-type {
            background-color: var(--research-blue) !important;
            border-color: var(--research-blue) !important;
        }
        [data-testid="stSidebar"] [data-testid="stCheckbox"] label[data-selected="true"] > div:first-of-type svg,
        [data-testid="stSidebar"] [data-testid="stCheckbox"] label:has(input:checked) > div:first-of-type svg {
            stroke: #FFFFFF !important;
            fill: none !important;
        }
        [data-testid="stSidebar"] [data-testid="stCheckbox"] [data-testid="stMarkdownContainer"] p {
            color: var(--research-text) !important;
            font-size: 0.84rem !important;
            font-weight: 500 !important;
            line-height: 1.4 !important;
            margin: 0 !important;
        }

        /* Sidebar Expander (Gelişmiş filtreler) */
        [data-testid="stSidebar"] [data-testid="stExpander"] {
            background: transparent !important;
            border: 1px solid #DCE5EF !important;
            border-radius: 9px !important;
            box-shadow: none !important;
            margin-top: 0.55rem;
            margin-bottom: 0.4rem;
            overflow: hidden;
        }
        [data-testid="stSidebar"] [data-testid="stExpander"] details summary {
            background: #F4F7FB !important;
            padding: 0.45rem 0.65rem !important;
            border-radius: 8px !important;
            min-height: auto !important;
            cursor: pointer !important;
            transition: background 0.15s ease;
        }
        [data-testid="stSidebar"] [data-testid="stExpander"] details summary:hover {
            background: #EAF0F7 !important;
        }
        [data-testid="stSidebar"] [data-testid="stExpander"] details summary p {
            font-size: 0.81rem !important;
            font-weight: 600 !important;
            color: var(--research-navy) !important;
        }
        [data-testid="stSidebar"] [data-testid="stExpander"] details summary svg,
        [data-testid="stSidebar"] [data-testid="stExpander"] details summary span[data-testid="stIconMaterial"] {
            color: var(--research-blue) !important;
            font-size: 1.1rem !important;
        }
        [data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stExpanderDetails"] {
            background: #FFFFFF !important;
            padding: 0.75rem 0.65rem 0.6rem !important;
            border-top: 1px solid #E6EEF6 !important;
        }
        [data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stWidgetLabel"] p {
            font-size: 0.8rem !important;
            font-weight: 600 !important;
            color: var(--research-navy) !important;
        }

        [data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--research-card);
            border-color: var(--research-border) !important;
            border-radius: 14px;
            box-shadow: 0 5px 18px rgba(31, 53, 86, 0.035);
        }
        [data-testid="stExpander"] {
            background: var(--research-card) !important;
            border: 1px solid var(--research-border);
            border-radius: 11px;
            margin-bottom: 0.75rem;
            overflow: hidden;
        }
        [data-testid="stExpander"] details,
        [data-testid="stExpander"] details > summary {
            background: #FFFFFF !important;
        }
        [data-testid="stExpander"] details summary {
            padding: 0.45rem 0.25rem;
            color: var(--research-navy);
            font-weight: 560;
            min-height: 2.8rem;
        }
        [data-testid="stExpander"] details summary p {
            color: var(--research-navy) !important;
            line-height: 1.45;
            margin: 0;
            overflow-wrap: anywhere;
            white-space: normal;
        }
        [data-testid="stProgressBarTrack"] { background-color: #E8EDF3 !important; }
        [data-testid="stProgressBarTrack"] > div { background-color: var(--research-blue) !important; }

        .section-kicker {
            color: var(--research-blue);
            font-size: 0.72rem;
            font-weight: 750;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            margin-bottom: 0.2rem;
        }
        .metric-card {
            min-height: 104px;
            padding: 1.05rem 1.1rem;
            background: #FFFFFF;
            border: 1px solid var(--research-border);
            border-radius: 13px;
            box-shadow: 0 3px 12px rgba(31, 53, 86, 0.025);
        }
        .metric-card.primary { background: var(--research-soft-blue); border-color: #C9DDF4; }
        .metric-card.positive { background: var(--research-soft-green); border-color: #CBE7D8; }
        .metric-card.negative { background: var(--research-soft-red); border-color: #F0D2D2; }
        .metric-card.warning { background: var(--research-soft-amber); border-color: #EEDDAF; }
        .metric-card.neutral { background: #F6F8FB; }
        .metric-label { color: var(--research-muted); font-size: 0.8rem; font-weight: 560; line-height: 1.35; }
        .metric-value {
            color: var(--research-text);
            font-size: 1.42rem;
            font-weight: 720;
            line-height: 1.25;
            margin-top: 0.42rem;
            overflow-wrap: anywhere;
        }
        .metric-card.featured .metric-value { color: var(--research-blue); font-size: 1.7rem; }
        .metric-help {
            color: var(--research-muted);
            font-size: 0.85rem;
            line-height: 1.5;
            margin: 0.7rem 0 0.1rem;
        }
        .status-badge {
            display: inline-flex;
            align-items: center;
            padding: 0.25rem 0.55rem;
            border-radius: 6px;
            font-size: 0.78rem;
            font-weight: 650;
            margin: 0 0.35rem 0.8rem 0;
        }
        .status-badge.positive { color: #276749; background: var(--research-soft-green); }
        .status-badge.negative { color: #9B3A3A; background: var(--research-soft-red); }
        .status-badge.warning { color: #805B14; background: var(--research-soft-amber); }
        .status-badge.neutral { color: #586779; background: #EEF2F6; }
        .review-column-header {
            padding: 0.8rem 0.9rem 0.75rem;
            margin-bottom: 0.8rem;
            background: #F4F7FB;
            border: 1px solid #DCE5EF;
            border-top: 3px solid #8297AE;
            border-radius: 10px;
        }
        .review-column-header.positive {
            background: #F3FAF6;
            border-color: #D4EBDD;
            border-top-color: #68A984;
        }
        .review-column-header.negative {
            background: #FEF6F6;
            border-color: #F1DADA;
            border-top-color: #C77D7D;
        }
        .review-column-title {
            color: var(--research-navy);
            font-size: 0.78rem;
            font-weight: 760;
            letter-spacing: 0.065em;
            line-height: 1.25;
            text-transform: uppercase;
        }
        .review-column-count {
            color: var(--research-muted);
            font-size: 0.82rem;
            font-variant-numeric: tabular-nums;
            margin-top: 0.2rem;
        }
        /* Passage cards. In Streamlit the keyed bordered container IS the
           stVerticalBlock element, so the card is styled directly (not a child). */
        [class*="st-key-review_card_"] {
            background: #F7F9FC;
            border: 1px solid #D5DEE9 !important;
            border-left: 4px solid #8297AE !important;
            border-radius: 12px;
            box-shadow: 0 1px 3px rgba(31, 53, 86, 0.04);
            margin-bottom: 0.8rem;
            padding: 0.45rem 0.55rem 0.55rem !important;
            transition: box-shadow 0.15s ease;
        }
        [class*="st-key-review_card_"]:hover {
            box-shadow: 0 4px 12px rgba(31, 53, 86, 0.08);
        }
        [class*="st-key-review_card_relevant_"] {
            background: #F4FAF6;
            border-color: #CBE5D5 !important;
            border-left-color: #68A984 !important;
        }
        [class*="st-key-review_card_irrelevant_"] {
            background: #FEF6F6;
            border-color: #F0D4D4 !important;
            border-left-color: #C77D7D !important;
        }
        /* Open card: one white, fully outlined box in the column colour. */
        [class*="st-key-review_card_unreviewed_open_"] {
            background: #FFFFFF;
            border: 1.5px solid #8297AE !important;
            box-shadow: 0 6px 18px rgba(75, 98, 128, 0.14);
            padding: 0.6rem 0.8rem 0.8rem !important;
        }
        [class*="st-key-review_card_relevant_open_"] {
            background: #FFFFFF;
            border: 1.5px solid #68A984 !important;
            box-shadow: 0 6px 18px rgba(80, 150, 112, 0.16);
            padding: 0.6rem 0.8rem 0.8rem !important;
        }
        [class*="st-key-review_card_irrelevant_open_"] {
            background: #FFFFFF;
            border: 1.5px solid #C77D7D !important;
            box-shadow: 0 6px 18px rgba(190, 100, 100, 0.16);
            padding: 0.6rem 0.8rem 0.8rem !important;
        }
        [class*="st-key-card_toggle_"] button {
            align-items: flex-start;
            background: transparent !important;
            border: 0 !important;
            box-shadow: none !important;
            color: var(--research-text) !important;
            height: auto;
            justify-content: flex-start;
            min-height: 0;
            border-radius: 9px !important;
            padding: 0.55rem 0.6rem !important;
            text-align: left;
            white-space: normal;
            width: 100%;
        }
        [class*="st-key-card_toggle_"] button:hover {
            background: rgba(59, 80, 110, 0.05) !important;
        }
        [class*="st-key-card_toggle_"] [data-testid="stMarkdownContainer"] {
            width: 100%;
        }
        [class*="st-key-card_toggle_"] [data-testid="stMarkdownContainer"] p {
            color: var(--research-text) !important;
            line-height: 1.42;
            margin: 0 0 0.36rem;
            overflow-wrap: anywhere;
            text-align: left;
            white-space: normal;
        }
        [class*="st-key-card_toggle_"] [data-testid="stMarkdownContainer"] p:first-child {
            color: var(--research-muted) !important;
            font-size: 0.74rem;
            font-weight: 650;
            letter-spacing: 0.025em;
        }
        [class*="st-key-card_toggle_"] [data-testid="stMarkdownContainer"] p:nth-child(2) {
            color: var(--research-navy) !important;
            font-size: 0.91rem;
            font-weight: 700;
        }
        [class*="st-key-card_toggle_"] [data-testid="stMarkdownContainer"] p:last-child {
            color: #52647B !important;
            font-size: 0.8rem;
            font-weight: 450;
            margin-bottom: 0;
        }
        .review-empty {
            color: var(--research-muted);
            background: #F8FAFD;
            border: 1px dashed #DCE5EF;
            border-radius: 9px;
            font-size: 0.84rem;
            line-height: 1.5;
            padding: 0.85rem 0.9rem;
        }
        .passage-source-line {
            color: var(--research-muted);
            font-size: 0.76rem;
            font-weight: 650;
            letter-spacing: 0.025em;
            margin: 0.35rem 0 0.45rem;
        }
        .passage-divider {
            border-top: 1px solid #E1E8F0;
            margin: 0.1rem 0.15rem 0.7rem;
        }
        .passage-text {
            color: var(--research-text);
            background: #F7F9FC;
            border-left: 3px solid #8297AE;
            border-radius: 0 8px 8px 0;
            font-size: 0.98rem;
            line-height: 1.62;
            padding: 1rem 1.1rem;
            margin: 0.2rem 0.15rem 0.7rem;
            white-space: pre-wrap;
        }
        .passage-text.positive { background: #F4FAF6; border-left-color: #68A984; }
        .passage-text.negative { background: #FEF6F6; border-left-color: #C77D7D; }
        .matched-term-line {
            color: var(--research-muted);
            font-size: 0.85rem;
            margin: 0 0 0.75rem;
        }
        .matched-term {
            color: var(--research-navy);
            background: var(--research-soft-blue);
            border: 1px solid #D3E2F3;
            border-radius: 5px;
            font-weight: 650;
            padding: 0.14rem 0.38rem;
        }
        .technical-grid {
            display: grid;
            grid-template-columns: minmax(120px, 0.7fr) minmax(0, 1.6fr);
            gap: 0.55rem 1rem;
            align-items: baseline;
            color: var(--research-text);
            font-size: 0.84rem;
        }
        .technical-label { color: var(--research-muted); font-weight: 600; }
        .technical-value {
            color: var(--research-navy);
            font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
            overflow-wrap: anywhere;
        }
        /* Technical details toggle affordance */
        [class*="st-key-technical_details_"] {
            margin: 0.6rem 0 0.4rem;
        }
        [class*="st-key-technical_details_"] label {
            display: flex !important;
            align-items: center !important;
            width: 100% !important;
            padding: 0.42rem 0.75rem !important;
            background: #F4F7FB !important;
            border: 1px solid #DCE5EF !important;
            border-radius: 7px !important;
            cursor: pointer !important;
            user-select: none;
            transition: all 0.15s ease;
        }
        [class*="st-key-technical_details_"] label:hover {
            background: #EAF0F7 !important;
            border-color: #CBD8E6 !important;
        }
        [class*="st-key-technical_details_"] label:has(input:checked) {
            background: #EEF4FA !important;
            border-color: #BFD3E6 !important;
        }
        /* Hide native switch track so only the chevron + label box is visible */
        [class*="st-key-technical_details_"] label > div:not([data-testid="stWidgetLabel"]) {
            display: none !important;
        }
        [class*="st-key-technical_details_"] [data-testid="stWidgetLabel"] {
            width: 100% !important;
        }
        [class*="st-key-technical_details_"] [data-testid="stMarkdownContainer"] p {
            color: #374B64 !important;
            font-size: 0.81rem !important;
            font-weight: 600 !important;
            letter-spacing: 0.01em;
            margin: 0 !important;
            line-height: 1.4 !important;
        }
        [class*="st-key-technical_panel_"] {
            background: #F8FAFD;
            border-color: #E2E8F0 !important;
            border-radius: 9px;
            box-shadow: none;
        }
        /* Pagination Controls (Sprint 4) */
        [class*="st-key-pagination_bar_"] {
            margin-top: 0.8rem;
            margin-bottom: 0.6rem;
            padding: 0.2rem 0.3rem !important;
            background: #F8FAFC !important;
            border: 1px solid #DCE5EF !important;
            border-radius: 9px !important;
        }
        .pagination-indicator {
            text-align: center;
            color: var(--research-navy);
            font-size: 0.80rem;
            font-weight: 650;
            line-height: 2.2rem;
            white-space: nowrap;
        }
        [class*="st-key-prev_page_"] button,
        [class*="st-key-next_page_"] button {
            color: var(--research-blue) !important;
            font-size: 0.80rem !important;
            font-weight: 600 !important;
            padding: 0.3rem 0.4rem !important;
            border-radius: 6px !important;
        }
        [class*="st-key-prev_page_"] button:disabled,
        [class*="st-key-next_page_"] button:disabled {
            color: #A0AEC0 !important;
            opacity: 0.45 !important;
        }
        .research-table-wrap {
            width: 100%;
            overflow-x: auto;
            margin: 0.45rem 0 1.4rem;
            border: 1px solid var(--research-border);
            border-radius: 11px;
            background: #FFFFFF;
        }
        .research-table {
            width: 100%;
            border-collapse: collapse;
            color: var(--research-text);
            font-size: 0.92rem;
        }
        .research-table thead th {
            background: #EEF3F9;
            color: var(--research-navy);
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.015em;
            padding: 0.8rem 1rem;
            text-align: left;
            white-space: nowrap;
        }
        .research-table tbody td {
            background: #FFFFFF;
            border-top: 1px solid #E8EDF3;
            padding: 0.78rem 1rem;
        }
        .research-table tbody tr:hover td { background: #F7FAFD; }
        .research-table tbody td:first-child { color: var(--research-navy); font-weight: 680; }
        .research-table .numeric { font-variant-numeric: tabular-nums; text-align: right; }
        [class*="st-key-relevant_"] button {
            background: #E7F5EC !important;
            border-color: #B7DCC5 !important;
            color: #276749 !important;
        }
        [class*="st-key-irrelevant_"] button {
            background: #FBEAEA !important;
            border-color: #E8C2C2 !important;
            color: #9B3A3A !important;
        }
        [class*="st-key-clear_"] button {
            background: #F4F6F8 !important;
            border-color: #DCE2E8 !important;
            color: #586779 !important;
        }
        [data-testid="stButton"] button { border-radius: 8px; font-weight: 600; }

        @media (max-width: 700px) {
            [data-testid="stMainBlockContainer"] { padding-top: 1rem; }
            .hero-panel { padding: 1.25rem; margin-bottom: 1.4rem; }
            .metric-card { min-height: auto; margin-bottom: 0.35rem; }
            .passage-text { padding: 0.85rem; }
            .review-column-header { margin-top: 0.35rem; }
            .technical-grid { grid-template-columns: 1fr; gap: 0.25rem; }
            .research-table thead th, .research-table tbody td { padding: 0.7rem 0.75rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_metric_card(
    label: str,
    value: Any,
    *,
    tone: str = "",
    featured: bool = False,
) -> None:
    classes = " ".join(
        part for part in ("metric-card", tone, "featured" if featured else "") if part
    )
    st.markdown(
        f'<div class="{classes}"><div class="metric-label">{escape(str(label))}</div>'
        f'<div class="metric-value">{escape(str(value))}</div></div>',
        unsafe_allow_html=True,
    )


def status_tone(status: str) -> str:
    return {"relevant": "positive", "irrelevant": "negative"}.get(status, "neutral")


def render_hero(text: dict[str, str]) -> None:
    """Render the compact research-product header."""
    st.markdown(
        '<div class="hero-panel">'
        f'<div class="hero-eyebrow">{escape(text["eyebrow"])}</div>'
        f'<div class="hero-title">{escape(text["title"])}</div>'
        f'<p class="hero-description">{escape(text["description"])}</p>'
        f'<p class="hero-methodology">{escape(text["methodology"])}</p>'
        '</div>',
        unsafe_allow_html=True,
    )


def render_sidebar_label(label: str) -> None:
    st.markdown(
        f'<div class="sidebar-section-label">{escape(label)}</div>',
        unsafe_allow_html=True,
    )


def render_light_table(
    headers: list[str],
    rows: list[list[Any]],
    *,
    numeric_columns: set[int] | None = None,
) -> None:
    """Render a responsive light table with presentation-only HTML."""
    numeric_columns = numeric_columns or set()
    head_html = "".join(f'<th scope="col">{escape(str(header))}</th>' for header in headers)
    body_rows = []
    for row in rows:
        cells = []
        for index, value in enumerate(row):
            class_name = ' class="numeric"' if index in numeric_columns else ""
            cells.append(f'<td{class_name}>{escape(str(value))}</td>')
        body_rows.append(f'<tr>{"".join(cells)}</tr>')
    st.markdown(
        '<div class="research-table-wrap"><table class="research-table">'
        f'<thead><tr>{head_html}</tr></thead>'
        f'<tbody>{"".join(body_rows)}</tbody>'
        '</table></div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Render helpers
# ---------------------------------------------------------------------------

def render_document_overview(
    doc_id: str,
    data: dict,
    language: str,
    text: dict[str, str],
) -> None:
    doc = data["document"]
    matches = data.get("matches", [])
    total = len(matches)

    st.subheader(text["document_overview"])
    # Review progress (live — do NOT cache)
    rev_summary = get_review_summary(doc_id, data)
    reviewed = rev_summary["overall"]["reviewed"]
    if total > 0:
        progress_frac = reviewed / total
    else:
        progress_frac = 0.0

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        render_metric_card(
            text["country"],
            COUNTRY_LABELS.get(doc_id, {}).get(language, doc.get("country", "—")),
        )
    with c2:
        render_metric_card(text["analysed_words"], f"{doc.get('total_analysis_words', 0):,}")
    with c3:
        render_metric_card(text["total_matches"], total)
    with c4:
        render_metric_card(text["total_segments"], f"{doc.get('total_segments', 0):,}")
    with c5:
        render_metric_card(text["review_progress"], f"{reviewed} / {total}", tone="primary")

    st.caption(f"{reviewed} / {total} {text['reviewed_suffix']}")
    st.progress(progress_frac)


def render_category_metrics(
    doc_id: str,
    data: dict,
    category: str,
    language: str,
    text: dict[str, str],
) -> None:
    summary = data.get("summary", {})
    cat_data = summary.get(category, {})

    st.markdown(
        f'<div class="section-kicker">{escape(text["category_heading"])}</div>',
        unsafe_allow_html=True,
    )
    st.subheader(category_label(category, language))
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_metric_card(
            text["frequency"],
            fmt_freq(cat_data.get("frequency_per_1000_words", 0)),
            tone="primary",
            featured=True,
        )
    with c2:
        render_metric_card(text["raw_mentions"], cat_data.get("raw_baseline_mentions", 0))
    with c3:
        render_metric_card(text["segment_hits"], cat_data.get("segment_hits", 0))
    with c4:
        render_metric_card(
            text["review_required"],
            cat_data.get("review_required_mentions", 0),
            tone="warning",
        )
    st.markdown(
        f'<p class="metric-help">{escape(text["frequency_help"])} '
        f'&nbsp;&middot;&nbsp; {escape(text["review_required_help"])}</p>',
        unsafe_allow_html=True,
    )


def render_human_verification(
    review_counts: dict[str, int],
    total_active_mentions: int,
    text: dict[str, str],
) -> None:
    """Render the live review summary for active passages."""
    st.subheader(text["human_verification"])
    v1, v2, v3, v4 = st.columns(4)
    with v1:
        render_metric_card(
            text["reviewed_passages"],
            f"{review_counts.get('reviewed', 0)} / {review_counts.get('total', 0)}",
            tone="primary",
        )
    with v2:
        render_metric_card(text["relevant_passages"], review_counts.get("relevant", 0), tone="positive")
    with v3:
        render_metric_card(text["irrelevant_passages"], review_counts.get("irrelevant", 0), tone="negative")
    with v4:
        render_metric_card(text["unreviewed_passages"], review_counts.get("unreviewed", 0), tone="neutral")

    st.caption(
        text["passage_summary_help"].format(
            passages=review_counts.get("total", 0),
            mentions=total_active_mentions,
        )
    )


def render_ranking(data: dict, language: str, text: dict[str, str]) -> None:
    st.subheader(text["threat_category_frequency"])
    cats = ordered_categories(data)
    summary = data.get("summary", {})

    rows: list[list[Any]] = []
    chart_rows: list[dict[str, Any]] = []
    display_categories: list[str] = []
    for cat in cats:
        freq = summary.get(cat, {}).get("frequency_per_1000_words", 0)
        raw  = summary.get(cat, {}).get("raw_baseline_mentions", 0)
        display_cat = category_label(cat, language)
        rows.append([display_cat, fmt_freq(freq), raw])
        display_categories.append(display_cat)
        chart_rows.append({"category": display_cat, "frequency": freq})

    render_light_table(
        [text["category"], text["frequency"], text["raw_mentions"]],
        rows,
        numeric_columns={1, 2},
    )

    import altair as alt  # bundled with Streamlit

    chart = (
        alt.Chart(alt.Data(values=chart_rows))
        .mark_bar(color="#4F7FC1", cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=alt.X(
                "category:N",
                sort=display_categories,
                axis=alt.Axis(labelAngle=0, title=None),
            ),
            y=alt.Y(
                "frequency:Q",
                title=text["frequency"],
                scale=alt.Scale(zero=True),
            ),
            tooltip=[
                alt.Tooltip("category:N", title=text["category"]),
                alt.Tooltip("frequency:Q", title=text["frequency"], format=".3f"),
            ],
        )
        .properties(height=285, background="#FFFFFF")
        .configure_view(stroke=None)
        .configure_axis(
            domainColor="#CBD5E1",
            gridColor="#E8EDF3",
            labelColor="#52647B",
            labelFontSize=12,
            tickColor="#CBD5E1",
            titleColor="#24354B",
            titleFontSize=12,
            titleFontWeight=600,
        )
    )
    st.altair_chart(chart, width="stretch")


def get_page_number(
    doc_id: str,
    category: str,
    status: str,
    total_items: int,
) -> tuple[int, int]:
    """Return (current_page, total_pages) clamped to valid 1-based bounds."""
    total_pages = max(1, (total_items + PAGE_SIZE - 1) // PAGE_SIZE)
    page_key = f"page_{doc_id}_{category}_{status}"
    current_page = st.session_state.get(page_key, 1)
    if not isinstance(current_page, int) or current_page < 1:
        current_page = 1
    elif current_page > total_pages:
        current_page = total_pages
    st.session_state[page_key] = current_page
    return current_page, total_pages


def change_page(page_key: str, new_page: int) -> None:
    st.session_state[page_key] = new_page


def render_pagination_controls(
    page_key: str,
    current_page: int,
    total_pages: int,
    text: dict[str, str],
) -> None:
    """Render compact, subtle pagination controls (< Önceki  Sayfa 1 / 97  Sonraki >)."""
    if total_pages <= 1:
        return

    with st.container(key=f"pagination_bar_{page_key}"):
        col_prev, col_info, col_next = st.columns([1.1, 1.4, 1.1], vertical_alignment="center")
        with col_prev:
            st.button(
                text["prev_page"],
                key=f"prev_{page_key}",
                disabled=(current_page <= 1),
                type="tertiary",
                width="stretch",
                on_click=change_page,
                args=(page_key, current_page - 1),
            )
        with col_info:
            page_info_str = f"{text['page_prefix']} {current_page} / {total_pages}"
            st.markdown(
                f'<div class="pagination-indicator">{escape(page_info_str)}</div>',
                unsafe_allow_html=True,
            )
        with col_next:
            st.button(
                text["next_page"],
                key=f"next_{page_key}",
                disabled=(current_page >= total_pages),
                type="tertiary",
                width="stretch",
                on_click=change_page,
                args=(page_key, current_page + 1),
            )


def render_passage_card(
    doc_id: str,
    passage: dict,
    current_status: str,
    text: dict[str, str],
) -> None:
    """Render one unique passage card with compact term badges and full traceability."""
    pkey = passage["passage_key"]
    seg_id = passage["segment_id"]
    cat = passage["category"]
    pdf_p = passage.get("page_number_pdf")
    printed_p = passage.get("page_number_printed")
    segment_text = passage.get("segment_text", "")
    preview = passage_preview(segment_text)
    display_status = status_label(current_status, text)
    is_active = st.session_state.get("active_passage_id") == pkey
    diag = passage.get("review_diagnostics", {})

    term_counts = passage.get("term_counts", {})
    terms_summary = ", ".join(
        f"{term} ({cnt})" if cnt > 1 else str(term)
        for term, cnt in term_counts.items()
    )

    safe_id = f"{cat}__{seg_id}".replace(" ", "_")

    chevron = "▾" if is_active else "▸"
    card_label = (
        f"{chevron} PDF p.{escape_markdown_label(pdf_p)}\n\n"
        f"**{escape_markdown_label(terms_summary or '—')}**\n\n"
        f"{escape_markdown_label(preview or '—')}"
    )

    with st.container(
        border=True,
        # "open_" only changes the CSS hook so an expanded card can be styled.
        key=f"review_card_{current_status}_{'open_' if is_active else ''}{safe_id}",
    ):
        st.button(
            card_label,
            key=f"card_toggle_{safe_id}",
            type="tertiary",
            width="stretch",
            on_click=toggle_active_passage,
            args=(pkey,),
        )

        if not is_active:
            return

        st.markdown('<div class="passage-divider"></div>', unsafe_allow_html=True)

        source_parts = [f"PDF p.{pdf_p}"]
        if printed_p:
            source_parts.append(f"{text['printed_page']}: {printed_p}")
        st.markdown(
            f'<div class="passage-source-line">{escape(text["source_information"])}'
            f' &middot; {escape(" · ".join(source_parts))}</div>',
            unsafe_allow_html=True,
        )

        # The full source paragraph stays verbatim and visually dominant.
        st.markdown(
            f'<div class="passage-text {status_tone(current_status)}">'
            f'{escape(str(segment_text))}</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            f'<p class="matched-term-line">{escape(text["matched_terms"])} ({len(passage["matches"])}): '
            f'<span class="matched-term">{escape(str(terms_summary))}</span></p>',
            unsafe_allow_html=True,
        )

        badges = (
            f'<span class="status-badge {status_tone(current_status)}">'
            f'{escape(display_status)}</span>'
        )
        if any(m.get("requires_review", False) for m in passage["matches"]):
            badges += (
                f'<span class="status-badge warning">'
                f'{escape(text["requires_review"])}</span>'
            )
        if diag.get("source") == "legacy_conflict":
            badges += (
                f'<span class="status-badge warning">'
                f'{escape(text["legacy_conflict_badge"])}</span>'
            )
        st.markdown(badges, unsafe_allow_html=True)

        # Review action buttons
        b1, b2, b3 = st.columns(3)
        with b1:
            if st.button(
                text["relevant"],
                key=f"relevant_{safe_id}",
                type="primary",
                width="stretch",
            ):
                try:
                    set_passage_review_status(doc_id, cat, seg_id, "relevant")
                except Exception as exc:
                    st.error(f"{text['error_setting_review']}: {exc}")
                else:
                    st.rerun()
        with b2:
            if st.button(
                text["irrelevant"],
                key=f"irrelevant_{safe_id}",
                width="stretch",
            ):
                try:
                    set_passage_review_status(doc_id, cat, seg_id, "irrelevant")
                except Exception as exc:
                    st.error(f"{text['error_setting_review']}: {exc}")
                else:
                    st.rerun()
        with b3:
            if st.button(
                text["clear"],
                key=f"clear_{safe_id}",
                type="tertiary",
                width="stretch",
            ):
                try:
                    clear_passage_review(doc_id, cat, seg_id, passage["matches"])
                except Exception as exc:
                    st.error(f"{text['error_clearing_review']}: {exc}")
                else:
                    st.rerun()

        # Collapsible technical details with individual match traceability
        is_tech_open = st.session_state.get(f"technical_details_{safe_id}", False)
        tech_chevron = "▾" if is_tech_open else "▸"
        show_technical = st.toggle(
            f"{tech_chevron} {text['technical_details']}",
            value=False,
            key=f"technical_details_{safe_id}",
        )
        if show_technical:
            tech_rows: list[tuple[str, Any]] = [(text["pdf_page"], pdf_p)]
            if printed_p:
                tech_rows.append((text["printed_page"], printed_p))
            tech_rows.extend([
                ("Segment ID", seg_id),
                ("Category", cat),
                ("Passage Key", pkey),
                ("Matches in Passage", len(passage["matches"])),
                ("Review Source", diag.get("source", "passage")),
                (text["status"], display_status),
            ])
            tech_html = "".join(
                f'<div class="technical-label">{escape(str(label))}</div>'
                f'<div class="technical-value">{escape(str(value))}</div>'
                for label, value in tech_rows
            )

            match_rows = []
            for idx, m in enumerate(passage["matches"], start=1):
                offsets_str = f"{m.get('char_start', 0)}–{m.get('char_end', 0)}"
                match_rows.append([
                    f"#{idx}",
                    m.get("pattern_id", "—"),
                    m.get("matched_text", "—"),
                    offsets_str,
                    m.get("tier", "—"),
                    "Yes" if m.get("requires_review") else "No",
                    "Yes" if m.get("count_in_raw_baseline", True) else "No",
                ])

            with st.container(border=True, key=f"technical_panel_{safe_id}"):
                st.markdown(
                    f'<div class="technical-grid">{tech_html}</div>',
                    unsafe_allow_html=True,
                )
                st.write("")
                render_light_table(
                    ["#", "Pattern", text["matched_terms"], text["offsets"], "Tier", text["requires_review"], text["in_raw_baseline"]],
                    match_rows,
                )


def render_review_card(
    doc_id: str,
    match_or_passage: dict,
    current_status: str,
    text: dict[str, str],
) -> None:
    """Backward compatibility wrapper delegating to render_passage_card."""
    if "passage_key" in match_or_passage:
        render_passage_card(doc_id, match_or_passage, current_status, text)
    else:
        # Wrap single match as single-match passage
        passage = {
            "segment_id": match_or_passage.get("segment_id", "—"),
            "category": match_or_passage.get("category", "—"),
            "passage_key": make_passage_key(match_or_passage.get("category", ""), match_or_passage.get("segment_id", "")),
            "page_number_pdf": match_or_passage.get("page_number_pdf"),
            "page_number_printed": match_or_passage.get("page_number_printed"),
            "segment_text": match_or_passage.get("segment_text", ""),
            "matches": [match_or_passage],
            "term_counts": {match_or_passage.get("matched_text", ""): 1},
        }
        render_passage_card(doc_id, passage, current_status, text)


def render_passages(
    doc_id: str,
    category: str,
    grouped_passages: dict[str, list[dict]],
    language: str,
    text: dict[str, str],
) -> None:
    st.subheader(text["source_passages"])

    grouped = grouped_passages
    total_active = sum(len(items) for items in grouped.values())
    if total_active == 0:
        st.info(text["no_passages"])
        st.session_state["active_passage_id"] = None
        return

    columns_config = (
        (
            "unreviewed",
            text["review_board_unreviewed"],
            "neutral",
            text["empty_unreviewed"],
        ),
        (
            "relevant",
            text["review_board_relevant"],
            "positive",
            text["empty_relevant"],
        ),
        (
            "irrelevant",
            text["review_board_irrelevant"],
            "negative",
            text["empty_irrelevant"],
        ),
    )

    # Collect visible page passage keys across all columns to safely clean up active_passage_id
    visible_page_keys = set()
    columns_page_passages = {}

    for status, label, tone, empty_text in columns_config:
        passages = grouped[status]
        total_items = len(passages)
        current_page, total_pages = get_page_number(
            doc_id, category, status, total_items
        )
        start_idx = (current_page - 1) * PAGE_SIZE
        end_idx = start_idx + PAGE_SIZE
        page_items = passages[start_idx:end_idx]
        columns_page_passages[status] = (page_items, current_page, total_pages)
        for p in page_items:
            visible_page_keys.add(p["passage_key"])

    # Safe active card cleanup if open card is no longer on visible page
    if st.session_state.get("active_passage_id") not in visible_page_keys:
        st.session_state["active_passage_id"] = None

    with st.container(key="review_board"):
        board_columns = st.columns(3, gap="medium")
        for column, (status, label, tone, empty_text) in zip(
            board_columns,
            columns_config,
            strict=True,
        ):
            passages = grouped[status]
            total_items = len(passages)
            page_passages, current_page, total_pages = columns_page_passages[status]
            page_key = f"page_{doc_id}_{category}_{status}"

            with column:
                st.markdown(
                    f'<div class="review-column-header {tone}">'
                    f'<div class="review-column-title">{escape(label)}</div>'
                    f'<div class="review-column-count">{total_items} '
                    f'{escape(text["passage_count"])}</div></div>',
                    unsafe_allow_html=True,
                )
                if not passages:
                    st.markdown(
                        f'<div class="review-empty">{escape(empty_text)}</div>',
                        unsafe_allow_html=True,
                    )
                    continue

                for passage in page_passages:
                    render_passage_card(doc_id, passage, status, text)

                if total_pages > 1:
                    render_pagination_controls(
                        page_key, current_page, total_pages, text
                    )


def render_comparison(
    all_data: dict[str, dict | None],
    language: str,
    text: dict[str, str],
) -> None:
    st.subheader(text["cross_document_comparison"])
    st.caption(text["comparison_subtitle"])

    available: dict[str, dict] = {
        doc_id: d for doc_id, d in all_data.items() if d is not None
    }
    if len(available) < 2:
        st.info(text["comparison_unavailable"])
        return

    first_data = next(iter(available.values()))
    cats = ordered_categories(first_data)

    import altair as alt  # bundled with Streamlit

    country_labels = [
        COUNTRY_LABELS.get(doc_id, {}).get(language, doc_id)
        for doc_id in available
    ]
    rows: list[list[Any]] = []
    chart_rows: list[dict[str, Any]] = []
    display_categories: list[str] = []
    for cat in cats:
        display_cat = category_label(cat, language)
        display_categories.append(display_cat)
        row: list[Any] = [display_cat]
        for doc_id, d in available.items():
            label = COUNTRY_LABELS.get(doc_id, {}).get(language, doc_id)
            freq  = d["summary"].get(cat, {}).get("frequency_per_1000_words", 0)
            row.append(fmt_freq(freq))
            chart_rows.append({
                "category": display_cat,
                "country": label,
                "frequency": freq,
            })
        rows.append(row)

    render_light_table(
        [text["category"], *country_labels],
        rows,
        numeric_columns=set(range(1, len(country_labels) + 1)),
    )

    color_map = {
        "latvia_sdc_2023": "#6FA8DC",
        "uk_sdr_2025": "#4F7FC1",
        "netherlands_dwp_2024": "#86C5A5",
        "japan_doj_2026": "#D9822B",
    }
    country_colors = [color_map.get(doc_id, "#6FA8DC") for doc_id in available]
    comparison_chart = (
        alt.Chart(alt.Data(values=chart_rows))
        .mark_bar(cornerRadiusTopLeft=2, cornerRadiusTopRight=2)
        .encode(
            x=alt.X(
                "category:N",
                sort=display_categories,
                axis=alt.Axis(labelAngle=0, title=None),
            ),
            xOffset=alt.XOffset("country:N", sort=country_labels),
            y=alt.Y(
                "frequency:Q",
                title=text["frequency"],
                scale=alt.Scale(zero=True),
            ),
            color=alt.Color(
                "country:N",
                scale=alt.Scale(domain=country_labels, range=country_colors),
                legend=alt.Legend(
                    title=None,
                    orient="top",
                    direction="horizontal",
                    labelColor="#52647B",
                ),
            ),
            tooltip=[
                alt.Tooltip("category:N", title=text["category"]),
                alt.Tooltip("country:N", title=text["country"]),
                alt.Tooltip("frequency:Q", title=text["frequency"], format=".3f"),
            ],
        )
        .properties(height=320, background="#FFFFFF")
        .configure_view(stroke=None)
        .configure_axis(
            domainColor="#CBD5E1",
            gridColor="#E8EDF3",
            labelColor="#52647B",
            labelFontSize=12,
            tickColor="#CBD5E1",
            titleColor="#24354B",
            titleFontSize=12,
            titleFontWeight=600,
        )
    )
    st.altair_chart(comparison_chart, width="stretch")
    st.caption(text["comparison_methodology"])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(
        page_title="Security Research Assistant",
        page_icon="🔍",
        layout="wide",
    )
    apply_ui_styles()

    with st.sidebar:
        render_sidebar_label("Language / Dil")
        language_name = st.selectbox(
            "Language / Dil",
            options=["Türkçe", "English"],
            index=0,
            key="ui_language",
            label_visibility="collapsed",
        )

    language = "tr" if language_name == "Türkçe" else "en"
    text = UI_TEXT[language]

    previous_language = st.session_state.get("_last_ui_language", language)
    language_changed = previous_language != language
    preferred_document = (
        st.session_state.get(f"document_selector_{previous_language}")
        if language_changed else None
    )
    preferred_category = (
        st.session_state.get(f"category_selector_{previous_language}")
        if language_changed else None
    )
    if language_changed:
        for widget_name in (
            "document_selector",
            "category_selector",
        ):
            st.session_state.pop(f"{widget_name}_{language}", None)
    st.session_state["_last_ui_language"] = language

    render_hero(text)

    # Load all analysis data upfront (cached — stable)
    all_data: dict[str, dict | None] = {
        doc_id: load_analysis(doc_id) for doc_id in DOCUMENTS
    }

    # ---- Sidebar ----
    with st.sidebar:
        st.divider()
        render_sidebar_label(text["document"])

        document_ids = list(DOCUMENTS)
        document_index = (
            document_ids.index(preferred_document)
            if preferred_document in document_ids else 0
        )
        doc_id = st.selectbox(
            text["document"],
            options=document_ids,
            index=document_index,
            format_func=lambda value: document_label(value, language),
            key=f"document_selector_{language}",
            label_visibility="collapsed",
        )

        data = all_data.get(doc_id)
        if data is None:
            st.error(text["analysis_missing"])
            st.stop()

        render_sidebar_label(text["category"])
        cats = ordered_categories(data)
        category_index = (
            cats.index(preferred_category)
            if preferred_category in cats else 0
        )
        category = st.selectbox(
            text["category"],
            options=cats,
            index=category_index,
            format_func=lambda value: category_label(value, language),
            key=f"category_selector_{language}",
            label_visibility="collapsed",
        )

        st.divider()
        render_sidebar_label(text["filters"])
        show_review_only = st.checkbox(
            text["show_review_required"],
            value=False,
            key="show_review_required",
        )
        include_review_only = st.checkbox(
            text["include_review_only"],
            value=False,
            key="include_review_only",
        )
        review_status_filter = "all" 

    # ---- Error guard ----
    if data is None:
        st.error(text["analysis_missing"])
        st.stop()

    # ---- Document overview + review progress ----
    with st.container(border=True):
        render_document_overview(doc_id, data, language, text)

    st.write("")

    # ---- Category metrics + human verification summary ----
    with st.container(border=True):
        render_category_metrics(doc_id, data, category, language, text)

    st.write("")

    # ---- Category ranking ----
    with st.container(border=True):
        render_ranking(data, language, text)

    st.write("")

    # Load review store snapshot ONCE per rerun
    review_store_data = load_reviews(doc_id)

    # 1. Filter matches according to strict filter order
    active_matches = get_active_matches(
        data,
        category,
        show_review_only=show_review_only,
        include_review_only=include_review_only,
    )
    total_active_mentions = len(active_matches)

    # 2. Group active matches into unique passages (1 passage = 1 card)
    active_passages = group_matches_into_passages(active_matches, category)

    # 3. Resolve passage status from review snapshot
    grouped_passages, review_counts = group_passages_by_status(
        doc_id,
        category,
        active_passages,
        review_store_data,
        review_status_filter=review_status_filter,
    )

    # ---- Human verification ----
    with st.container(border=True):
        render_human_verification(
            review_counts,
            total_active_mentions,
            text,
        )

    st.write("")

    # ---- Source passages with VERIFY buttons ----
    with st.container(border=True):
        render_passages(
            doc_id,
            category,
            grouped_passages,
            language,
            text,
        )

    st.write("")

    # ---- Cross-document comparison ----
    with st.container(border=True):
        render_comparison(all_data, language, text)


if __name__ == "__main__":
    main()
