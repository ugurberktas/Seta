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
# Document config
# ---------------------------------------------------------------------------

DOCUMENTS: dict[str, str] = {
    "latvia_sdc_2023": "Latvia — State Defence Concept 2023–2027",
    "uk_sdr_2025": "United Kingdom — Strategic Defence Review 2025",
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


def status_label(status: str) -> str:
    return {"relevant": "Relevant", "irrelevant": "Irrelevant"}.get(status, "Unreviewed")


# ---------------------------------------------------------------------------
# Render helpers
# ---------------------------------------------------------------------------

def render_document_overview(doc_id: str, data: dict) -> None:
    doc = data["document"]
    matches = data.get("matches", [])
    total = len(matches)

    st.subheader("Document Overview")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Country", doc.get("country", "—"))
    c2.metric("Analysed words", f"{doc.get('total_analysis_words', 0):,}")
    c3.metric("Total matches", total)
    c4.metric("Source passages", f"{doc.get('total_segments', 0):,}")

    # Review progress (live — do NOT cache)
    rev_summary = get_review_summary(doc_id, data)
    reviewed = rev_summary["overall"]["reviewed"]
    if total > 0:
        progress_frac = reviewed / total
    else:
        progress_frac = 0.0

    st.write(f"**Review progress:** {reviewed} / {total} reviewed")
    st.progress(progress_frac)


def render_category_metrics(doc_id: str, data: dict, category: str) -> None:
    summary = data.get("summary", {})
    cat_data = summary.get(category, {})

    st.subheader(f"Category: {category}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Frequency / 1,000 words", fmt_freq(cat_data.get("frequency_per_1000_words", 0)))
    c2.metric("Raw mentions", cat_data.get("raw_baseline_mentions", 0))
    c3.metric("Segment hits", cat_data.get("segment_hits", 0))
    c4.metric("Review-required", cat_data.get("review_required_mentions", 0))

    # Human Verification summary for this category (live)
    rev_summary = get_review_summary(doc_id, data)
    cat_rev = rev_summary["categories"].get(category, {})

    st.write("**Human Verification**")
    v1, v2, v3, v4 = st.columns(4)
    v1.metric("Reviewed", cat_rev.get("reviewed", 0))
    v2.metric("Relevant", cat_rev.get("relevant", 0))
    v3.metric("Irrelevant", cat_rev.get("irrelevant", 0))
    v4.metric("Unreviewed", cat_rev.get("unreviewed", 0))


def render_ranking(data: dict) -> None:
    st.subheader("Threat Category Frequency")
    cats = ordered_categories(data)
    summary = data.get("summary", {})

    rows = []
    chart_data: dict[str, list] = {"Category": [], "Frequency / 1,000 words": []}
    for cat in cats:
        freq = summary.get(cat, {}).get("frequency_per_1000_words", 0)
        raw  = summary.get(cat, {}).get("raw_baseline_mentions", 0)
        rows.append({"Category": cat, "Frequency / 1,000 words": fmt_freq(freq), "Raw mentions": raw})
        chart_data["Category"].append(cat)
        chart_data["Frequency / 1,000 words"].append(freq)

    st.dataframe(rows, width="stretch", hide_index=True)

    import pandas as pd  # bundled with Streamlit
    df_chart = pd.DataFrame(chart_data).set_index("Category")
    st.bar_chart(df_chart)


def render_passages(
    doc_id: str,
    data: dict,
    category: str,
    show_review_only: bool,
    include_review_only: bool,
    review_status_filter: str,
) -> None:
    st.subheader("Source Passages")

    matches = [m for m in data.get("matches", []) if m["category"] == category]

    # Checkbox filters
    if show_review_only:
        matches = [m for m in matches if m.get("requires_review", False)]
    elif not include_review_only:
        matches = [m for m in matches if m.get("count_in_raw_baseline", True)]

    # Review status filter
    if review_status_filter != "All":
        wanted = review_status_filter.lower()  # "relevant" | "irrelevant" | "unreviewed"
        matches = [
            m for m in matches
            if get_review_status(doc_id, m["match_id"]) == wanted
        ]

    if not matches:
        st.info("No source passages match the current filters.")
        return

    for m in matches:
        mid       = m["match_id"]
        pdf_p     = m.get("page_number_pdf")
        printed_p = m.get("page_number_printed")
        matched   = m.get("matched_text", "")
        cat       = m.get("category", "")

        # Live status (never cached)
        current_status = get_review_status(doc_id, mid)

        if printed_p and printed_p != pdf_p:
            title = f"PDF p.{pdf_p} / printed p.{printed_p} · {cat} · {matched}"
        else:
            title = f"PDF p.{pdf_p} · {cat} · {matched}"

        with st.expander(title):
            # Metadata row
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Segment ID:** `{m.get('segment_id', '—')}`")
                st.write(f"**Pattern ID:** `{m.get('pattern_id', '—')}`")
                st.write(f"**Tier:** `{m.get('tier', '—')}`")
            with col2:
                st.write(f"**Requires review:** `{m.get('requires_review', False)}`")
                st.write(f"**In raw baseline:** `{m.get('count_in_raw_baseline', False)}`")
                st.write(f"**Status:** {status_label(current_status)}")

            # Passage text
            st.write("**Segment text:**")
            st.write(m.get("segment_text", ""))
            st.caption(f"Matched term: `{matched}`")

            # VERIFY buttons
            b1, b2, b3 = st.columns(3)
            with b1:
                if st.button("Relevant", key=f"relevant_{mid}"):
                    try:
                        set_review_status(doc_id, mid, "relevant")
                    except Exception as exc:
                        st.error(f"Error setting review: {exc}")
                    else:
                        st.rerun()
            with b2:
                if st.button("Irrelevant", key=f"irrelevant_{mid}"):
                    try:
                        set_review_status(doc_id, mid, "irrelevant")
                    except Exception as exc:
                        st.error(f"Error setting review: {exc}")
                    else:
                        st.rerun()
            with b3:
                if st.button("Clear", key=f"clear_{mid}"):
                    try:
                        clear_review(doc_id, mid)
                    except Exception as exc:
                        st.error(f"Error clearing review: {exc}")
                    else:
                        st.rerun()


def render_comparison(all_data: dict[str, dict | None]) -> None:
    st.divider()
    st.subheader("Cross-document comparison")

    available: dict[str, dict] = {
        doc_id: d for doc_id, d in all_data.items() if d is not None
    }
    if len(available) < 2:
        st.info("Both documents must be analysed to show a comparison.")
        return

    first_data = next(iter(available.values()))
    cats = ordered_categories(first_data)

    import pandas as pd

    rows = []
    for cat in cats:
        row: dict[str, Any] = {"Category": cat}
        for doc_id, d in available.items():
            label = DOCUMENTS.get(doc_id, doc_id)
            freq  = d["summary"].get(cat, {}).get("frequency_per_1000_words", 0)
            row[label] = fmt_freq(freq)
        rows.append(row)

    st.dataframe(rows, width="stretch", hide_index=True)
    st.caption(
        "Frequencies are normalized as category mentions per 1,000 analysed words."
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(
        page_title="Security Research Assistant",
        page_icon="🔍",
        layout="wide",
    )

    st.title("Security Research Assistant")
    st.write(
        "Deterministic threat-frequency analysis with source traceability "
        "and human verification."
    )
    st.caption(
        "This PoC uses a compact English dictionary and does not reproduce "
        "SETA's original multilingual dictionary."
    )

    # Load all analysis data upfront (cached — stable)
    all_data: dict[str, dict | None] = {
        doc_id: load_analysis(doc_id) for doc_id in DOCUMENTS
    }

    # ---- Sidebar ----
    with st.sidebar:
        st.header("Filters")

        doc_label = st.selectbox(
            "Document",
            options=list(DOCUMENTS.values()),
            index=0,
        )
        doc_id = next(k for k, v in DOCUMENTS.items() if v == doc_label)

        data = all_data.get(doc_id)
        if data is None:
            st.error("Analysis output not found for this document.")
            st.stop()

        cats = ordered_categories(data)
        category = st.selectbox("Category", options=cats, index=0)

    # ---- Error guard ----
    if data is None:
        st.error("Analysis output not found for this document.")
        st.stop()

    # ---- Document overview + review progress ----
    render_document_overview(doc_id, data)
    st.divider()

    # ---- Category ranking ----
    render_ranking(data)
    st.divider()

    # ---- Category metrics + human verification summary ----
    render_category_metrics(doc_id, data, category)
    st.divider()

    # ---- Passage filters ----
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        show_review_only = st.checkbox("Show review-required matches only", value=False)
    with fc2:
        include_review_only = st.checkbox("Include review-only matches", value=False)
    with fc3:
        review_status_filter = st.selectbox(
            "Review status",
            options=["All", "Unreviewed", "Relevant", "Irrelevant"],
            index=0,
        )

    # ---- Source passages with VERIFY buttons ----
    render_passages(
        doc_id, data, category,
        show_review_only, include_review_only, review_status_filter,
    )

    # ---- Cross-document comparison ----
    render_comparison(all_data)


if __name__ == "__main__":
    main()
