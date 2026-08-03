from __future__ import annotations

from .models import StoryCostEstimate, StoryGenerationRequest, StoryProviderMetrics


PRICING_VERSION = "openai-pricing-2026-08-02"
PRICING_SOURCE = "https://developers.openai.com/api/docs/pricing"

# USD per 1M tokens. Keep this centralized and treat every display as an estimate.
MODEL_PRICES_USD_PER_1M = {
    "gpt-5.6-luna": {"input": 0.10, "cached_input": 0.01, "output": 0.60},
    "gpt-5.6-terra": {"input": 1.00, "cached_input": 0.10, "output": 6.00},
    "gpt-5.6-sol": {"input": 2.50, "cached_input": 0.25, "output": 15.00},
}


def pricing_snapshot(model: str) -> dict[str, object]:
    prices = MODEL_PRICES_USD_PER_1M.get(model)
    return {
        "pricing_table_version": PRICING_VERSION,
        "source": PRICING_SOURCE,
        "model": model,
        "currency": "USD",
        "unit": "1M tokens",
        "prices": prices or {},
        "estimate_note": "Estimate only. Actual billed cost may differ.",
    }


class StoryCostEstimator:
    def estimate_pre_request(self, request: StoryGenerationRequest) -> StoryCostEstimate:
        prices = MODEL_PRICES_USD_PER_1M.get(request.model)
        snapshot = pricing_snapshot(request.model)
        if not prices:
            return StoryCostEstimate(
                model=request.model,
                estimated_cost_usd=None,
                pricing_snapshot=snapshot,
                message="pricing unavailable",
            )
        # Conservative local estimate. The actual SDK usage is recorded after the request.
        estimated_input_tokens = max(800, len(request.theme) * 2 + 1200)
        estimated_output_tokens = max(request.max_output_tokens, 1024)
        cost = (
            estimated_input_tokens / 1_000_000 * prices["input"]
            + estimated_output_tokens / 1_000_000 * prices["output"]
        )
        return StoryCostEstimate(
            model=request.model,
            estimated_cost_usd=round(cost, 6),
            pricing_snapshot=snapshot,
            message="pre-request estimate",
        )

    def estimate_from_usage(self, model: str, metrics: StoryProviderMetrics) -> float | None:
        prices = MODEL_PRICES_USD_PER_1M.get(model)
        if not prices:
            return None
        input_tokens = metrics.input_tokens or 0
        cached = metrics.cached_input_tokens or 0
        output_tokens = metrics.output_tokens or 0
        uncached_input = max(0, input_tokens - cached)
        cost = (
            uncached_input / 1_000_000 * prices["input"]
            + cached / 1_000_000 * prices["cached_input"]
            + output_tokens / 1_000_000 * prices["output"]
        )
        return round(cost, 6)
