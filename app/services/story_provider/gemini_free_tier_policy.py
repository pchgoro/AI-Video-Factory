from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .gemini_model_catalog import FREE_TIER_AVAILABLE, GeminiModelMetadata


PROJECT_TIER_USER_CONFIRMED_FREE = "user_confirmed_free"
BILLING_USER_CONFIRMED_DISABLED = "user_confirmed_disabled"
CHARGE_RISK_LOW = "low"
CHARGE_RISK_UNKNOWN = "unknown"


@dataclass(frozen=True)
class GeminiFreeTierDecision:
    allowed: bool
    error_code: str = ""
    message: str = ""
    model_free_tier_status: str = "unknown"
    project_tier_status: str = "unknown"
    billing_status: str = "unknown"
    charge_risk: str = CHARGE_RISK_UNKNOWN

    def to_state_fields(self) -> dict[str, object]:
        return {
            "model_free_tier_status": self.model_free_tier_status,
            "project_tier_status": self.project_tier_status,
            "billing_status": self.billing_status,
            "charge_risk": self.charge_risk,
        }


def api_key_fingerprint(api_key: str) -> str:
    value = str(api_key or "").strip()
    if not value:
        return ""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


class GeminiFreeTierPolicy:
    def evaluate(
        self,
        *,
        metadata: GeminiModelMetadata | None,
        api_key: str,
        free_tier_only: bool,
        project_free_confirmed: bool,
        billing_disabled_confirmed: bool,
        confirmation_key_fingerprint: str,
        local_cap_reached: bool,
        quota_exhausted: bool,
    ) -> GeminiFreeTierDecision:
        model_status = metadata.free_tier_status if metadata is not None else "unknown"
        project_status = PROJECT_TIER_USER_CONFIRMED_FREE if project_free_confirmed else "unknown"
        billing_status = BILLING_USER_CONFIRMED_DISABLED if billing_disabled_confirmed else "unknown"
        current_fingerprint = api_key_fingerprint(api_key)
        charge_risk = CHARGE_RISK_LOW if project_free_confirmed and billing_disabled_confirmed else CHARGE_RISK_UNKNOWN

        if not free_tier_only:
            return GeminiFreeTierDecision(
                allowed=True,
                model_free_tier_status=model_status,
                project_tier_status=project_status,
                billing_status=billing_status,
                charge_risk=charge_risk,
            )
        if metadata is None:
            return self._deny("gemini_free_tier_unknown", "Free-tier-only mode blocks uncataloged Gemini models.", model_status, project_status, billing_status)
        if metadata.free_tier_status != FREE_TIER_AVAILABLE:
            return self._deny("gemini_free_tier_unavailable", "Selected Gemini model is not confirmed for Free Tier.", model_status, project_status, billing_status)
        if not metadata.structured_outputs:
            return self._deny("gemini_structured_outputs_unsupported", "Selected Gemini model does not support Structured Outputs.", model_status, project_status, billing_status)
        if not project_free_confirmed:
            return self._deny("gemini_project_tier_unconfirmed", "Confirm in Google AI Studio that this API key's project is on Free Tier.", model_status, project_status, billing_status)
        if not billing_disabled_confirmed:
            return self._deny("gemini_billing_unconfirmed", "Confirm that billing is not enabled for this Gemini API project.", model_status, project_status, billing_status)
        if not confirmation_key_fingerprint or confirmation_key_fingerprint != current_fingerprint:
            return self._deny("gemini_key_confirmation_required", "Gemini API key changed or was not confirmed; reconfirm Free Tier and billing status.", model_status, project_status, billing_status)
        if local_cap_reached:
            return self._deny("gemini_local_daily_cap_reached", "Local Gemini safety cap reached for today.", model_status, project_status, billing_status)
        if quota_exhausted:
            return self._deny("gemini_quota_exhausted", "Gemini quota appears exhausted; retry after the quota reset.", model_status, project_status, billing_status)
        return GeminiFreeTierDecision(
            allowed=True,
            model_free_tier_status=model_status,
            project_tier_status=project_status,
            billing_status=billing_status,
            charge_risk=CHARGE_RISK_LOW,
        )

    def _deny(self, code: str, message: str, model_status: str, project_status: str, billing_status: str) -> GeminiFreeTierDecision:
        return GeminiFreeTierDecision(
            allowed=False,
            error_code=code,
            message=message,
            model_free_tier_status=model_status,
            project_tier_status=project_status,
            billing_status=billing_status,
            charge_risk=CHARGE_RISK_UNKNOWN,
        )
