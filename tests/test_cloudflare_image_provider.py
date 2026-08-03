from __future__ import annotations

import base64
import json
import logging

import pytest

from services.image_generation.cloudflare_provider import CLOUDFLARE_API_HOST, FLUX_1_SCHNELL, CloudflareWorkersAIProvider
from services.image_generation.models import ImageGenerationError, ImageGenerationSettings


def test_missing_cloudflare_credentials_do_not_configure(monkeypatch) -> None:
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)

    status = CloudflareWorkersAIProvider(load_env=False).validate_configuration()

    assert status.configured is False


def test_flux_model_settings_allow_only_steps() -> None:
    provider = CloudflareWorkersAIProvider()

    provider.validate_model_settings(ImageGenerationSettings(model=FLUX_1_SCHNELL, steps=4))

    with pytest.raises(ImageGenerationError):
        provider.validate_model_settings(ImageGenerationSettings(model=FLUX_1_SCHNELL, steps=9))


def test_cloudflare_endpoint_host_is_fixed() -> None:
    assert CLOUDFLARE_API_HOST == "api.cloudflare.com"
    assert "openai" not in CLOUDFLARE_API_HOST


def test_json_base64_response_is_decoded() -> None:
    provider = CloudflareWorkersAIProvider()
    payload = {"success": True, "result": {"image": base64.b64encode(b"abc").decode("ascii")}}

    image_bytes, content_type = provider._decode_response(json.dumps(payload).encode("utf-8"), "application/json", 1024)

    assert image_bytes == b"abc"
    assert content_type == "image/jpeg"


def test_binary_image_response_is_supported() -> None:
    provider = CloudflareWorkersAIProvider()

    image_bytes, content_type = provider._decode_response(b"abc", "image/png", 1024)

    assert image_bytes == b"abc"
    assert content_type == "image/png"


def test_invalid_content_type_is_rejected() -> None:
    provider = CloudflareWorkersAIProvider()

    with pytest.raises(ImageGenerationError) as exc:
        provider._decode_response(b"abc", "text/plain", 1024)

    assert exc.value.retryable is False


def test_allocation_exceeded_429_is_not_retryable() -> None:
    provider = CloudflareWorkersAIProvider()
    error = provider.classify_error(429, {"errors": [{"code": "3036", "message": "Account limited"}]})

    assert error.code == "allocation_exceeded"
    assert error.retryable is False


def test_normal_429_is_retryable() -> None:
    provider = CloudflareWorkersAIProvider()
    error = provider.classify_error(429, {"errors": [{"code": "10000", "message": "rate limited"}]})

    assert error.retryable is True


def test_nsfw_prompt_rejection_is_not_reported_as_invalid_parameter() -> None:
    provider = CloudflareWorkersAIProvider()
    error = provider.classify_error(
        400,
        {"errors": [{"code": "AiError", "message": "AiError: Input prompt contains NSFW content."}]},
    )

    assert error.code == "prompt_rejection"
    assert error.retryable is False
    assert "プロンプト" in str(error)


def test_api_token_is_not_logged(monkeypatch, caplog) -> None:
    token = "secret-token"
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", token)
    provider = CloudflareWorkersAIProvider(logging.getLogger("test.cloudflare"))

    with caplog.at_level(logging.INFO):
        provider.logger.info("configured")

    assert token not in caplog.text


def test_openai_sdk_is_not_imported_in_provider_source() -> None:
    import inspect
    import services.image_generation.cloudflare_provider as module

    source = inspect.getsource(module)
    assert "openai" not in source.lower()
