from __future__ import annotations

from services.story_provider.gemini_free_tier_policy import GeminiFreeTierPolicy, api_key_fingerprint
from services.story_provider.gemini_model_catalog import get_gemini_model_metadata


def _decision(**kwargs):
    return GeminiFreeTierPolicy().evaluate(
        metadata=kwargs.get("metadata", get_gemini_model_metadata("gemini-3.5-flash-lite")),
        api_key=kwargs.get("api_key", "key-1"),
        free_tier_only=kwargs.get("free_tier_only", True),
        project_free_confirmed=kwargs.get("project_free_confirmed", True),
        billing_disabled_confirmed=kwargs.get("billing_disabled_confirmed", True),
        confirmation_key_fingerprint=kwargs.get("fingerprint", api_key_fingerprint("key-1")),
        local_cap_reached=kwargs.get("local_cap_reached", False),
        quota_exhausted=kwargs.get("quota_exhausted", False),
    )


def test_free_tier_guard_allows_confirmed_safe_state() -> None:
    result = _decision()

    assert result.allowed is True
    assert result.model_free_tier_status == "available"
    assert result.project_tier_status == "user_confirmed_free"
    assert result.billing_status == "user_confirmed_disabled"
    assert result.charge_risk == "low"


def test_free_tier_guard_blocks_unknown_model_and_custom_model() -> None:
    result = _decision(metadata=None)

    assert result.allowed is False
    assert result.error_code == "gemini_free_tier_unknown"


def test_free_tier_guard_requires_project_and_billing_confirmation() -> None:
    assert _decision(project_free_confirmed=False).error_code == "gemini_project_tier_unconfirmed"
    assert _decision(billing_disabled_confirmed=False).error_code == "gemini_billing_unconfirmed"


def test_api_key_change_invalidates_confirmation() -> None:
    result = _decision(fingerprint=api_key_fingerprint("old-key"))

    assert result.allowed is False
    assert result.error_code == "gemini_key_confirmation_required"
    assert api_key_fingerprint("key-1") not in {"key-1", "old-key"}


def test_local_cap_and_quota_exhaustion_block_generation() -> None:
    assert _decision(local_cap_reached=True).error_code == "gemini_local_daily_cap_reached"
    assert _decision(quota_exhausted=True).error_code == "gemini_quota_exhausted"
