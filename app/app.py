"""
app/app.py
----------
Security Research Assistant — Streamlit UI v2 (Overview + Source Passages + VERIFY)

Run from repo root:
    .venv/bin/streamlit run app/app.py
"""

from __future__ import annotations

import json
from html import escape
import sys
from pathlib import Path
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
}

COUNTRY_LABELS: dict[str, dict[str, str]] = {
    "latvia_sdc_2023": {"tr": "Letonya", "en": "Latvia"},
    "uk_sdr_2025": {"tr": "Birleşik Krallık", "en": "United Kingdom"},
    "netherlands_dwp_2024": {"tr": "Hollanda", "en": "Netherlands"},
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
        "source_passages": "Kaynak Pasajlar",
        "review_progress": "İnceleme ilerlemesi",
        "reviewed_suffix": "incelendi",
        "category_heading": "Kategori",
        "threat_category_frequency": "Tehdit Kategorisi Sıklığı",
        "frequency": "1.000 kelime başına sıklık",
        "raw_mentions": "Ham bahsetme sayısı",
        "segment_hits": "Pasaj eşleşmeleri",
        "review_required": "İnceleme gerekli",
        "human_verification": "İnsan Doğrulaması",
        "reviewed": "İncelendi",
        "relevant": "İlgili",
        "irrelevant": "İlgisiz",
        "unreviewed": "İncelenmedi",
        "show_review_required": "Yalnızca inceleme gerektiren eşleşmeleri göster",
        "include_review_only": "Yalnızca inceleme amaçlı eşleşmeleri dahil et",
        "review_status": "İnceleme durumu",
        "all": "Tümü",
        "no_passages": "Geçerli filtrelerle eşleşen kaynak pasaj bulunamadı.",
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
        "comparison_unavailable": "Karşılaştırma için en az iki belgenin analiz edilmiş olması gerekir.",
        "comparison_methodology": "Sonuçlar kompakt bir İngilizce sözlüğe dayanır ve kaynak raporun özgün çok dilli analizinden farklı olabilir.",
        "analysis_missing": "Bu belge için analiz çıktısı bulunamadı.",
        "error_setting_review": "İnceleme durumu ayarlanamadı",
        "error_clearing_review": "İnceleme durumu temizlenemedi",
    },
    "en": {
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
        "source_passages": "Source Passages",
        "review_progress": "Review progress",
        "reviewed_suffix": "reviewed",
        "category_heading": "Category",
        "threat_category_frequency": "Threat Category Frequency",
        "frequency": "Frequency / 1,000 words",
        "raw_mentions": "Raw mentions",
        "segment_hits": "Segment hits",
        "review_required": "Review-required",
        "human_verification": "Human Verification",
        "reviewed": "Reviewed",
        "relevant": "Relevant",
        "irrelevant": "Irrelevant",
        "unreviewed": "Unreviewed",
        "show_review_required": "Show review-required matches only",
        "include_review_only": "Include review-only matches",
        "review_status": "Review status",
        "all": "All",
        "no_passages": "No source passages match the current filters.",
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
        "comparison_unavailable": "At least two documents must be analysed to show a comparison.",
        "comparison_methodology": "Results use a compact English dictionary and may differ from the source report's original multilingual analysis.",
        "analysis_missing": "Analysis output not found for this document.",
        "error_setting_review": "Error setting review",
        "error_clearing_review": "Error clearing review",
    },
}

SCOPE = "core_body"

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


def apply_ui_styles() -> None:
    """Apply a small, presentation-only theme on top of Streamlit defaults."""
    st.markdown(
        """
        <style>
        :root {
            --research-bg: #F7F9FC;
            --research-card: #FFFFFF;
            --research-border: #E5EAF0;
            --research-text: #243247;
            --research-muted: #66758A;
            --research-blue: #3B6EA8;
        }

        [data-testid="stAppViewContainer"] {
            background: var(--research-bg);
            color: var(--research-text);
        }
        [data-testid="stHeader"] { background: rgba(247, 249, 252, 0.92); }
        [data-testid="stSidebar"] {
            background: #FFFFFF;
            border-right: 1px solid var(--research-border);
        }
        [data-testid="stMainBlockContainer"] {
            max-width: 1240px;
            padding-top: 2.4rem;
            padding-bottom: 4rem;
        }
        h1, h2, h3, h4, h5, h6 {
            color: var(--research-text) !important;
            letter-spacing: -0.015em;
        }
        h1 { font-size: clamp(1.9rem, 3.2vw, 2.5rem) !important; margin-bottom: 0.35rem !important; }
        h2, h3 { margin-top: 0.2rem !important; }
        p, label, [data-testid="stCaptionContainer"] { color: var(--research-text) !important; }
        [data-testid="stCaptionContainer"] { color: var(--research-muted) !important; }
        hr { border-color: var(--research-border) !important; margin: 1.65rem 0 !important; }

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

        [data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--research-card);
            border-color: var(--research-border) !important;
            border-radius: 12px;
            box-shadow: none;
        }
        [data-testid="stExpander"] {
            background: var(--research-card);
            border: 1px solid var(--research-border);
            border-radius: 10px;
            margin-bottom: 0.65rem;
        }
        [data-testid="stExpander"] details summary { padding: 0.35rem 0.2rem; }
        [data-testid="stProgressBarTrack"] { background-color: #E8EDF3 !important; }
        [data-testid="stProgressBarTrack"] > div { background-color: var(--research-blue) !important; }

        .section-kicker {
            color: var(--research-blue);
            font-size: 0.76rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 0.15rem;
        }
        .metric-card {
            min-height: 98px;
            padding: 1rem 1.05rem;
            background: #FFFFFF;
            border: 1px solid var(--research-border);
            border-radius: 10px;
        }
        .metric-card.primary { background: #F1F6FC; border-color: #C9D9EB; }
        .metric-card.positive { background: #F0F8F3; border-color: #CBE5D4; }
        .metric-card.negative { background: #FDF3F3; border-color: #F0CECE; }
        .metric-card.warning { background: #FFF8E8; border-color: #ECD9A4; }
        .metric-card.neutral { background: #F7F8FA; }
        .metric-label { color: var(--research-muted); font-size: 0.82rem; line-height: 1.3; }
        .metric-value {
            color: var(--research-text);
            font-size: 1.45rem;
            font-weight: 650;
            line-height: 1.25;
            margin-top: 0.42rem;
            overflow-wrap: anywhere;
        }
        .metric-card.featured .metric-value { color: var(--research-blue); font-size: 1.75rem; }
        .status-badge {
            display: inline-flex;
            align-items: center;
            padding: 0.25rem 0.55rem;
            border-radius: 6px;
            font-size: 0.78rem;
            font-weight: 650;
            margin: 0 0.35rem 0.8rem 0;
        }
        .status-badge.positive { color: #276749; background: #E7F5EC; }
        .status-badge.negative { color: #9B3A3A; background: #FBEAEA; }
        .status-badge.warning { color: #805B14; background: #FFF2CF; }
        .status-badge.neutral { color: #586779; background: #EDF1F5; }
        .passage-text {
            color: #2E3A4B;
            background: #FAFBFD;
            border-left: 3px solid #AFC5DE;
            border-radius: 0 8px 8px 0;
            font-size: 1rem;
            line-height: 1.72;
            padding: 1rem 1.15rem;
            margin: 0.35rem 0 0.75rem;
            white-space: pre-wrap;
        }
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
            [data-testid="stMainBlockContainer"] { padding-top: 1.4rem; }
            .metric-card { min-height: auto; margin-bottom: 0.35rem; }
            .passage-text { padding: 0.85rem; }
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
        render_metric_card(text["source_passages"], f"{doc.get('total_segments', 0):,}")
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


def render_human_verification(
    doc_id: str,
    data: dict,
    category: str,
    text: dict[str, str],
) -> None:
    """Render the live review summary without changing stored review state."""
    rev_summary = get_review_summary(doc_id, data)
    cat_rev = rev_summary["categories"].get(category, {})

    st.subheader(text["human_verification"])
    v1, v2, v3, v4 = st.columns(4)
    with v1:
        render_metric_card(text["reviewed"], cat_rev.get("reviewed", 0), tone="primary")
    with v2:
        render_metric_card(text["relevant"], cat_rev.get("relevant", 0), tone="positive")
    with v3:
        render_metric_card(text["irrelevant"], cat_rev.get("irrelevant", 0), tone="negative")
    with v4:
        render_metric_card(text["unreviewed"], cat_rev.get("unreviewed", 0), tone="neutral")


def render_ranking(data: dict, language: str, text: dict[str, str]) -> None:
    st.subheader(text["threat_category_frequency"])
    cats = ordered_categories(data)
    summary = data.get("summary", {})

    rows = []
    chart_data: dict[str, list] = {text["category"]: [], text["frequency"]: []}
    for cat in cats:
        freq = summary.get(cat, {}).get("frequency_per_1000_words", 0)
        raw  = summary.get(cat, {}).get("raw_baseline_mentions", 0)
        display_cat = category_label(cat, language)
        rows.append({
            text["category"]: display_cat,
            text["frequency"]: fmt_freq(freq),
            text["raw_mentions"]: raw,
        })
        chart_data[text["category"]].append(display_cat)
        chart_data[text["frequency"]].append(freq)

    st.dataframe(rows, width="stretch", hide_index=True)

    import pandas as pd  # bundled with Streamlit
    df_chart = pd.DataFrame(chart_data).set_index(text["category"])
    st.bar_chart(df_chart)


def render_passages(
    doc_id: str,
    data: dict,
    category: str,
    show_review_only: bool,
    include_review_only: bool,
    review_status_filter: str,
    language: str,
    text: dict[str, str],
) -> None:
    st.subheader(text["source_passages"])

    matches = [m for m in data.get("matches", []) if m["category"] == category]

    # Checkbox filters
    if show_review_only:
        matches = [m for m in matches if m.get("requires_review", False)]
    elif not include_review_only:
        matches = [m for m in matches if m.get("count_in_raw_baseline", True)]

    # Review status filter
    if review_status_filter != "all":
        wanted = review_status_filter
        matches = [
            m for m in matches
            if get_review_status(doc_id, m["match_id"]) == wanted
        ]

    if not matches:
        st.info(text["no_passages"])
        return

    for m in matches:
        mid       = m["match_id"]
        pdf_p     = m.get("page_number_pdf")
        printed_p = m.get("page_number_printed")
        matched   = m.get("matched_text", "")
        cat       = m.get("category", "")
        display_cat = category_label(cat, language)

        # Live status (never cached)
        current_status = get_review_status(doc_id, mid)

        display_status = status_label(current_status, text)
        if printed_p and printed_p != pdf_p:
            title = f"PDF p.{pdf_p} / printed p.{printed_p} · {display_cat} · {matched} · {display_status}"
        else:
            title = f"PDF p.{pdf_p} · {display_cat} · {matched} · {display_status}"

        with st.expander(title):
            badges = (
                f'<span class="status-badge {status_tone(current_status)}">'
                f'{escape(display_status)}</span>'
            )
            if m.get("requires_review", False):
                badges += (
                    f'<span class="status-badge warning">'
                    f'{escape(text["requires_review"])}</span>'
                )
            st.markdown(badges, unsafe_allow_html=True)

            st.markdown(
                f'<div class="passage-text">{escape(str(m.get("segment_text", "")))}</div>',
                unsafe_allow_html=True,
            )
            st.caption(f"{text['matched_term']}: `{matched}`")

            with st.popover(text["technical_details"]):
                st.write(f"**{text['pdf_page']}:** `{pdf_p}`")
                if printed_p:
                    st.write(f"**{text['printed_page']}:** `{printed_p}`")
                st.write(f"**Segment ID:** `{m.get('segment_id', '—')}`")
                st.write(f"**Pattern ID:** `{m.get('pattern_id', '—')}`")
                st.write(f"**Tier:** `{m.get('tier', '—')}`")
                st.write(f"**{text['requires_review']}:** `{m.get('requires_review', False)}`")
                st.write(f"**{text['in_raw_baseline']}:** `{m.get('count_in_raw_baseline', False)}`")
                st.write(f"**{text['status']}:** {display_status}")

            # VERIFY buttons
            b1, b2, b3 = st.columns(3)
            with b1:
                if st.button(
                    text["relevant"],
                    key=f"relevant_{mid}",
                    type="primary",
                    width="stretch",
                ):
                    try:
                        set_review_status(doc_id, mid, "relevant")
                    except Exception as exc:
                        st.error(f"{text['error_setting_review']}: {exc}")
                    else:
                        st.rerun()
            with b2:
                if st.button(
                    text["irrelevant"],
                    key=f"irrelevant_{mid}",
                    width="stretch",
                ):
                    try:
                        set_review_status(doc_id, mid, "irrelevant")
                    except Exception as exc:
                        st.error(f"{text['error_setting_review']}: {exc}")
                    else:
                        st.rerun()
            with b3:
                if st.button(
                    text["clear"],
                    key=f"clear_{mid}",
                    type="tertiary",
                    width="stretch",
                ):
                    try:
                        clear_review(doc_id, mid)
                    except Exception as exc:
                        st.error(f"{text['error_clearing_review']}: {exc}")
                    else:
                        st.rerun()


def render_comparison(
    all_data: dict[str, dict | None],
    language: str,
    text: dict[str, str],
) -> None:
    st.subheader(text["cross_document_comparison"])

    available: dict[str, dict] = {
        doc_id: d for doc_id, d in all_data.items() if d is not None
    }
    if len(available) < 2:
        st.info(text["comparison_unavailable"])
        return

    first_data = next(iter(available.values()))
    cats = ordered_categories(first_data)

    import pandas as pd

    rows = []
    chart_rows = []
    for cat in cats:
        display_cat = category_label(cat, language)
        row: dict[str, Any] = {text["category"]: display_cat}
        chart_row: dict[str, Any] = {text["category"]: display_cat}
        for doc_id, d in available.items():
            label = COUNTRY_LABELS.get(doc_id, {}).get(language, doc_id)
            freq  = d["summary"].get(cat, {}).get("frequency_per_1000_words", 0)
            row[label] = fmt_freq(freq)
            chart_row[label] = freq
        rows.append(row)
        chart_rows.append(chart_row)

    st.dataframe(rows, width="stretch", hide_index=True)
    comparison_chart = pd.DataFrame(chart_rows).set_index(text["category"])
    st.bar_chart(comparison_chart, stack=False)
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
        st.markdown("#### Language / Dil")
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
    preferred_review_status = (
        st.session_state.get(f"review_status_filter_{previous_language}")
        if language_changed else None
    )
    if language_changed:
        for widget_name in (
            "document_selector",
            "category_selector",
            "review_status_filter",
        ):
            st.session_state.pop(f"{widget_name}_{language}", None)
    st.session_state["_last_ui_language"] = language

    st.title(text["title"])
    st.write(text["description"])
    st.caption(text["methodology"])

    # Load all analysis data upfront (cached — stable)
    all_data: dict[str, dict | None] = {
        doc_id: load_analysis(doc_id) for doc_id in DOCUMENTS
    }

    # ---- Sidebar ----
    with st.sidebar:
        st.divider()
        st.markdown(f"#### {text['document']}")

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

        st.markdown(f"#### {text['category']}")
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
        st.markdown(f"#### {text['filters']}")
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
        review_statuses = ["all", "unreviewed", "relevant", "irrelevant"]
        review_status_index = (
            review_statuses.index(preferred_review_status)
            if preferred_review_status in review_statuses else 0
        )
        review_status_filter = st.selectbox(
            text["review_status"],
            options=review_statuses,
            index=review_status_index,
            format_func=lambda value: {
                "all": text["all"],
                "unreviewed": text["unreviewed"],
                "relevant": text["relevant"],
                "irrelevant": text["irrelevant"],
            }[value],
            key=f"review_status_filter_{language}",
        )

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

    # ---- Human verification ----
    with st.container(border=True):
        render_human_verification(doc_id, data, category, text)

    st.write("")

    # ---- Source passages with VERIFY buttons ----
    with st.container(border=True):
        render_passages(
            doc_id, data, category,
            show_review_only, include_review_only, review_status_filter,
            language, text,
        )

    st.write("")

    # ---- Cross-document comparison ----
    with st.container(border=True):
        render_comparison(all_data, language, text)


if __name__ == "__main__":
    main()
