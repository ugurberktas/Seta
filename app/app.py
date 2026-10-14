"""
app/app.py
----------
Security Research Assistant — Streamlit UI v2 (Overview + Source Passages + VERIFY)

Run from repo root:
    .venv/bin/streamlit run app/app.py
"""

from __future__ import annotations

import json
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
        "description": "Kaynak izlenebilirliği ve insan doğrulamasıyla deterministik tehdit sıklığı analizi.",
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
        "cross_document_comparison": "Belgeler Arası Karşılaştırma",
        "comparison_unavailable": "Karşılaştırma için en az iki belgenin analiz edilmiş olması gerekir.",
        "comparison_methodology": "Sonuçlar kompakt bir İngilizce sözlüğe dayanır ve kaynak raporun özgün çok dilli analizinden farklı olabilir.",
        "analysis_missing": "Bu belge için analiz çıktısı bulunamadı.",
        "error_setting_review": "İnceleme durumu ayarlanamadı",
        "error_clearing_review": "İnceleme durumu temizlenemedi",
    },
    "en": {
        "title": "Security Research Assistant",
        "description": "Deterministic threat-frequency analysis with source traceability and human verification.",
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
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(text["country"], COUNTRY_LABELS.get(doc_id, {}).get(language, doc.get("country", "—")))
    c2.metric(text["analysed_words"], f"{doc.get('total_analysis_words', 0):,}")
    c3.metric(text["total_matches"], total)
    c4.metric(text["source_passages"], f"{doc.get('total_segments', 0):,}")

    # Review progress (live — do NOT cache)
    rev_summary = get_review_summary(doc_id, data)
    reviewed = rev_summary["overall"]["reviewed"]
    if total > 0:
        progress_frac = reviewed / total
    else:
        progress_frac = 0.0

    st.write(
        f"**{text['review_progress']}:** "
        f"{reviewed} / {total} {text['reviewed_suffix']}"
    )
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

    st.subheader(f"{text['category_heading']}: {category_label(category, language)}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(text["frequency"], fmt_freq(cat_data.get("frequency_per_1000_words", 0)))
    c2.metric(text["raw_mentions"], cat_data.get("raw_baseline_mentions", 0))
    c3.metric(text["segment_hits"], cat_data.get("segment_hits", 0))
    c4.metric(text["review_required"], cat_data.get("review_required_mentions", 0))

    # Human Verification summary for this category (live)
    rev_summary = get_review_summary(doc_id, data)
    cat_rev = rev_summary["categories"].get(category, {})

    st.write(f"**{text['human_verification']}**")
    v1, v2, v3, v4 = st.columns(4)
    v1.metric(text["reviewed"], cat_rev.get("reviewed", 0))
    v2.metric(text["relevant"], cat_rev.get("relevant", 0))
    v3.metric(text["irrelevant"], cat_rev.get("irrelevant", 0))
    v4.metric(text["unreviewed"], cat_rev.get("unreviewed", 0))


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

        if printed_p and printed_p != pdf_p:
            title = f"PDF p.{pdf_p} / printed p.{printed_p} · {display_cat} · {matched}"
        else:
            title = f"PDF p.{pdf_p} · {display_cat} · {matched}"

        with st.expander(title):
            # Metadata row
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Segment ID:** `{m.get('segment_id', '—')}`")
                st.write(f"**Pattern ID:** `{m.get('pattern_id', '—')}`")
                st.write(f"**Tier:** `{m.get('tier', '—')}`")
            with col2:
                st.write(f"**{text['requires_review']}:** `{m.get('requires_review', False)}`")
                st.write(f"**{text['in_raw_baseline']}:** `{m.get('count_in_raw_baseline', False)}`")
                st.write(f"**{text['status']}:** {status_label(current_status, text)}")

            # Passage text
            st.write(f"**{text['segment_text']}:**")
            st.write(m.get("segment_text", ""))
            st.caption(f"{text['matched_term']}: `{matched}`")

            # VERIFY buttons
            b1, b2, b3 = st.columns(3)
            with b1:
                if st.button(text["relevant"], key=f"relevant_{mid}"):
                    try:
                        set_review_status(doc_id, mid, "relevant")
                    except Exception as exc:
                        st.error(f"{text['error_setting_review']}: {exc}")
                    else:
                        st.rerun()
            with b2:
                if st.button(text["irrelevant"], key=f"irrelevant_{mid}"):
                    try:
                        set_review_status(doc_id, mid, "irrelevant")
                    except Exception as exc:
                        st.error(f"{text['error_setting_review']}: {exc}")
                    else:
                        st.rerun()
            with b3:
                if st.button(text["clear"], key=f"clear_{mid}"):
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
    st.divider()
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
    st.bar_chart(comparison_chart)
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

    with st.sidebar:
        language_name = st.selectbox(
            "Language / Dil",
            options=["Türkçe", "English"],
            index=0,
            key="ui_language",
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
        st.header(text["filters"])

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
        )

        data = all_data.get(doc_id)
        if data is None:
            st.error(text["analysis_missing"])
            st.stop()

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
        )

    # ---- Error guard ----
    if data is None:
        st.error(text["analysis_missing"])
        st.stop()

    # ---- Document overview + review progress ----
    render_document_overview(doc_id, data, language, text)
    st.divider()

    # ---- Category ranking ----
    render_ranking(data, language, text)
    st.divider()

    # ---- Category metrics + human verification summary ----
    render_category_metrics(doc_id, data, category, language, text)
    st.divider()

    # ---- Passage filters ----
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        show_review_only = st.checkbox(
            text["show_review_required"],
            value=False,
            key="show_review_required",
        )
    with fc2:
        include_review_only = st.checkbox(
            text["include_review_only"],
            value=False,
            key="include_review_only",
        )
    with fc3:
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

    # ---- Source passages with VERIFY buttons ----
    render_passages(
        doc_id, data, category,
        show_review_only, include_review_only, review_status_filter,
        language, text,
    )

    # ---- Cross-document comparison ----
    render_comparison(all_data, language, text)


if __name__ == "__main__":
    main()
