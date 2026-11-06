"""
backend.tests.test_filter_matrix
--------------------------------
Comprehensive tests verifying the multi-stage filter pipeline:
1. Category match filtering
2. Review-only inclusion/exclusion
3. Review-required filtering
4. Unique passage grouping
5. Review status partitioning
"""

from __future__ import annotations

import pytest
from backend.app.services.analysis_service import analysis_service


def test_filter_matrix_japan_russia():
    """Verify all 4 combinations of include_review_only and show_review_only for Japan / Russia."""
    doc_id = "japan_doj_2026"
    cat = "Russia"

    # 1. Baseline: include_review_only=False, show_review_only=False
    res1 = analysis_service.get_passages(doc_id, cat, show_review_only=False, include_review_only=False)
    assert res1 is not None
    assert res1.total_raw_mentions == 890
    assert res1.total_passages == 269
    assert all(m.get("count_in_raw_baseline", True) for p in res1.passages for m in p.matches)

    # 2. All detected: include_review_only=True, show_review_only=False
    res2 = analysis_service.get_passages(doc_id, cat, show_review_only=False, include_review_only=True)
    assert res2 is not None
    assert res2.total_raw_mentions == 903  # 890 baseline + 13 review-only
    assert res2.total_passages == 272      # 269 baseline + 3 review-only-exclusive passages

    # 3. Review-required baseline: include_review_only=False, show_review_only=True
    # Must NOT reintroduce the 13 review-only matches!
    res3 = analysis_service.get_passages(doc_id, cat, show_review_only=True, include_review_only=False)
    assert res3 is not None
    assert res3.total_raw_mentions == 0
    assert res3.total_passages == 0

    # 4. All review-required: include_review_only=True, show_review_only=True
    res4 = analysis_service.get_passages(doc_id, cat, show_review_only=True, include_review_only=True)
    assert res4 is not None
    assert res4.total_raw_mentions == 13
    assert res4.total_passages == 10       # 13 review-only matches span 10 unique segments
    assert all(m.get("requires_review") for p in res4.passages for m in p.matches)


def test_filter_ordering_prevents_bypass():
    """Verify that review-required filter never bypasses review-only exclusion."""
    for doc_id in ("latvia_sdc_2023", "uk_sdr_2025", "netherlands_dwp_2024", "japan_doj_2026"):
        for cat in ("Russia", "China", "Cyber", "Hybrid", "Migration"):
            passages_res = analysis_service.get_passages(
                doc_id, cat, show_review_only=True, include_review_only=False
            )
            if passages_res and passages_res.total_passages > 0:
                for p in passages_res.passages:
                    for m in p.matches:
                        assert m.get("count_in_raw_baseline", True) is True
                        assert m.get("requires_review", False) is True
