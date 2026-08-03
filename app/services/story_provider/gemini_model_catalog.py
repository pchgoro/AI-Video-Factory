from __future__ import annotations

from dataclasses import asdict, dataclass


FREE_TIER_AVAILABLE = "available"
FREE_TIER_UNAVAILABLE = "unavailable"
FREE_TIER_UNKNOWN = "unknown"
PAID_ONLY = "paid_only"


@dataclass(frozen=True)
class GeminiModelMetadata:
    model_id: str
    stability: str
    structured_outputs: bool
    free_tier_status: str
    use_case: str
    metadata_checked_at: str
    source: str
    deprecated: bool = False
    supports_temperature: bool = True
    supports_thinking_config: bool = True
    rate_limit_info: str = "View active project limits in Google AI Studio. Local app cap is not Google quota."

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


CATALOG_SOURCE = "google_official_pricing_and_model_docs_2026-08-02"
CATALOG_CHECKED_AT = "2026-08-02"


_MODELS: dict[str, GeminiModelMetadata] = {
    "gemini-3.5-flash-lite": GeminiModelMetadata(
        model_id="gemini-3.5-flash-lite",
        stability="stable",
        structured_outputs=True,
        free_tier_status=FREE_TIER_AVAILABLE,
        use_case="High-frequency, low-cost story drafting",
        metadata_checked_at=CATALOG_CHECKED_AT,
        source=CATALOG_SOURCE,
    ),
    "gemini-3.5-flash": GeminiModelMetadata(
        model_id="gemini-3.5-flash",
        stability="stable",
        structured_outputs=True,
        free_tier_status=FREE_TIER_AVAILABLE,
        use_case="Balanced story quality and speed",
        metadata_checked_at=CATALOG_CHECKED_AT,
        source=CATALOG_SOURCE,
    ),
    "gemini-3.6-flash": GeminiModelMetadata(
        model_id="gemini-3.6-flash",
        stability="stable",
        structured_outputs=True,
        free_tier_status=FREE_TIER_AVAILABLE,
        use_case="Higher quality Flash story drafting",
        metadata_checked_at=CATALOG_CHECKED_AT,
        source=CATALOG_SOURCE,
    ),
}


def gemini_model_catalog() -> dict[str, GeminiModelMetadata]:
    return dict(_MODELS)


def get_gemini_model_metadata(model_id: str) -> GeminiModelMetadata | None:
    return _MODELS.get(str(model_id or "").strip())


def default_gemini_model() -> str:
    return "gemini-3.5-flash-lite"


def validate_gemini_model_id(model_id: str, allow_custom: bool = False) -> str:
    value = str(model_id or "").strip()
    if not value or len(value) > 120 or any(ord(ch) < 32 for ch in value):
        raise ValueError("Gemini model ID is invalid.")
    if value.startswith("http://") or value.startswith("https://") or "/" in value or "\\" in value:
        raise ValueError("Gemini model ID must not be a URL or path.")
    metadata = get_gemini_model_metadata(value)
    if metadata is None and not allow_custom:
        raise ValueError("Gemini model is not in the verified local catalog.")
    if metadata is not None and metadata.deprecated:
        raise ValueError("Gemini model is deprecated.")
    return value
