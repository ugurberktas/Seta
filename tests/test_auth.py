"""
tests/test_auth.py
------------------
Focused tests for:
1. Missing credentials => fail closed
2. Valid login verification
3. Invalid login verification
4. Successful login resets failure counter
5. 5 failures => temporary lockout (15 minutes)
6. Logout resets auth session state
7. Review action throttle permits normal use (<= 30 actions / 60s)
8. Review action throttle blocks excessive writes (> 30 actions / 60s)
9. Canonical analysis baselines remain unmodified
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

import auth
from auth import (
    are_credentials_configured,
    check_login_lockout,
    check_review_throttle,
    get_auth_credentials,
    is_authenticated,
    logout,
    record_login_failure,
    record_login_success,
    record_review_action,
    verify_credentials,
)


@pytest.fixture(autouse=True)
def clean_auth_env(monkeypatch):
    """Ensure clean credential environment for each test."""
    monkeypatch.delenv("APP_USERNAME", raising=False)
    monkeypatch.delenv("APP_PASSWORD", raising=False)


# ===========================================================================
# 1. Missing credentials => fail closed
# ===========================================================================

def test_missing_credentials_fails_closed():
    """When either or both credentials are missing, auth must fail closed."""
    # Neither configured
    assert get_auth_credentials() == (None, None)
    assert are_credentials_configured() is False
    assert verify_credentials("admin", "secret") is False

    # Only username configured
    import os
    os.environ["APP_USERNAME"] = "analyst"
    assert are_credentials_configured() is False
    assert verify_credentials("analyst", "secret") is False

    # Only password configured
    os.environ.pop("APP_USERNAME", None)
    os.environ["APP_PASSWORD"] = "secret123"
    assert are_credentials_configured() is False
    assert verify_credentials("analyst", "secret123") is False

    # Empty string configured
    os.environ["APP_USERNAME"] = "   "
    os.environ["APP_PASSWORD"] = "secret123"
    assert are_credentials_configured() is False
    assert verify_credentials("analyst", "secret123") is False


# ===========================================================================
# 2. Valid login verification
# ===========================================================================

def test_valid_login(monkeypatch):
    """Valid credentials must verify successfully with constant-time comparison."""
    monkeypatch.setenv("APP_USERNAME", "security_researcher")
    monkeypatch.setenv("APP_PASSWORD", "SuperSecurePassword123!")

    assert are_credentials_configured() is True
    assert verify_credentials("security_researcher", "SuperSecurePassword123!") is True
    # Strip whitespace on username allowed
    assert verify_credentials(" security_researcher ", "SuperSecurePassword123!") is True


# ===========================================================================
# 3. Invalid login verification
# ===========================================================================

def test_invalid_login(monkeypatch):
    """Invalid credentials must return False without leaking field specifics."""
    monkeypatch.setenv("APP_USERNAME", "correct_user")
    monkeypatch.setenv("APP_PASSWORD", "correct_password")

    # Wrong user
    assert verify_credentials("wrong_user", "correct_password") is False
    # Wrong password
    assert verify_credentials("correct_user", "wrong_password") is False
    # Both wrong
    assert verify_credentials("wrong_user", "wrong_password") is False
    # Empty inputs
    assert verify_credentials("", "") is False
    assert verify_credentials(None, None) is False


# ===========================================================================
# 4. Successful login resets failure counter
# ===========================================================================

def test_successful_login_resets_failure_counter():
    """A successful login must reset failure counter and clear any lockout."""
    session = {}
    base_time = 1000.0

    # Record 3 failures
    record_login_failure(session, now=base_time)
    record_login_failure(session, now=base_time + 10)
    record_login_failure(session, now=base_time + 20)
    assert len(session.get("_login_failures", [])) == 3

    # Successful login
    record_login_success(session, username="analyst")
    assert is_authenticated(session) is True
    assert session.get("auth_user") == "analyst"
    assert session.get("_login_failures") == []
    assert "_login_lockout_until" not in session


# ===========================================================================
# 5. 5 failures => temporary lockout (15 minutes)
# ===========================================================================

def test_five_failures_temporary_lockout():
    """5 failed attempts must trigger 15-minute temporary lockout."""
    session = {}
    t0 = 1000.0

    # Attempts 1 through 4: not locked
    for i in range(1, 5):
        is_locked, remaining = record_login_failure(session, now=t0 + i)
        assert is_locked is False
        assert remaining == 0

    # 5th attempt: triggers lockout
    is_locked, remaining = record_login_failure(session, now=t0 + 5)
    assert is_locked is True
    assert remaining == auth.LOGIN_LOCKOUT_SECONDS  # 900 seconds (15 minutes)

    # Subsequent check at t0 + 100 (still locked)
    locked_now, rem_now = check_login_lockout(session, now=t0 + 100)
    assert locked_now is True
    assert rem_now == (t0 + 5 + 900) - (t0 + 100)

    # After 15 minutes have passed (t0 + 906): lockout expired
    locked_later, rem_later = check_login_lockout(session, now=t0 + 906)
    assert locked_later is False
    assert rem_later == 0


# ===========================================================================
# 6. Logout resets auth session state
# ===========================================================================

def test_logout_resets_auth_session():
    """Logout must clear authentication state, user identity, and login inputs."""
    session = {
        "authenticated": True,
        "auth_user": "analyst",
        "_login_failures": [1.0, 2.0],
        "_login_lockout_until": 999.0,
        "login_username": "analyst",
        "login_password": "secret",
    }

    logout(session)
    assert is_authenticated(session) is False
    assert "auth_user" not in session
    assert "_login_failures" not in session
    assert "_login_lockout_until" not in session
    assert "login_username" not in session
    assert "login_password" not in session


# ===========================================================================
# 7. Review action throttle permits normal use
# ===========================================================================

def test_review_throttle_permits_normal_use():
    """Up to 30 review actions within 60 seconds must all be permitted."""
    session = {}
    t0 = 2000.0

    for i in range(30):
        allowed, retry_after = record_review_action(session, now=t0 + (i * 0.5))
        assert allowed is True
        assert retry_after == 0

    assert len(session["_review_action_timestamps"]) == 30


# ===========================================================================
# 8. Review action throttle blocks excessive writes
# ===========================================================================

def test_review_throttle_blocks_excessive_writes():
    """The 31st review action within 60 seconds must be blocked."""
    session = {}
    t0 = 3000.0

    # Perform 30 rapid review actions at t0
    for _ in range(30):
        allowed, _ = record_review_action(session, now=t0)
        assert allowed is True

    # 31st action at t0 + 10s: must be blocked with retry_after
    allowed, retry_after = record_review_action(session, now=t0 + 10.0)
    assert allowed is False
    assert retry_after == 50  # 60 - 10 = 50s remaining

    # Verify check_review_throttle also indicates blocked without recording
    can_act, wait_time = check_review_throttle(session, now=t0 + 10.0)
    assert can_act is False
    assert wait_time == 50

    # After 61 seconds have elapsed from t0, actions are permitted again
    allowed_later, _ = record_review_action(session, now=t0 + 61.0)
    assert allowed_later is True


# ===========================================================================
# 9. Canonical analysis baselines remain unmodified
# ===========================================================================

def test_canonical_analysis_unmodified_by_auth():
    """Auth additions must not alter canonical document metrics or threat matches."""
    checks = {
        "latvia_sdc_2023": {"words": 7108, "segments": 151, "matches": 71},
        "uk_sdr_2025": {"words": 41923, "segments": 822, "matches": 162},
        "netherlands_dwp_2024": {"words": 18465, "segments": 148, "matches": 130},
        "japan_doj_2026": {"words": 324705, "segments": 3746, "matches": 2956, "raw_baseline": 2943},
    }

    for doc_id, exp in checks.items():
        matches_file = PROJECT_ROOT / "data" / "processed" / f"{doc_id}_core_body_threat_matches.json"
        assert matches_file.exists(), f"Missing canonical file for {doc_id}"
        with matches_file.open(encoding="utf-8") as f:
            d = json.load(f)

        assert d["document"]["total_analysis_words"] == exp["words"]
        assert d["document"]["total_segments"] == exp["segments"]
        assert len(d["matches"]) == exp["matches"]

        if "raw_baseline" in exp:
            raw_sum = sum(
                cat.get("raw_baseline_mentions", 0)
                for cat in d["summary"].values()
                if isinstance(cat, dict)
            )
            assert raw_sum == exp["raw_baseline"]

    # Verify Japan / Russia
    with (PROJECT_ROOT / "data" / "processed" / "japan_doj_2026_core_body_threat_matches.json").open(encoding="utf-8") as f:
        j_data = json.load(f)
    russia = j_data["summary"]["Russia"]
    assert russia["raw_baseline_mentions"] == 890
    assert russia["segment_hits"] == 269
    assert abs(russia["frequency_per_1000_words"] - 2.740949) < 1e-6

