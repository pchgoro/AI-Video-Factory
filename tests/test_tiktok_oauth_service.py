from __future__ import annotations

import importlib
import os

import pytest

from services.tiktok.models import TikTokAuthError, TikTokTokenData, TikTokTokenStorageError
from services.tiktok.oauth_service import TikTokOAuthService
from services.tiktok.token_store import TikTokKeyringStore


class MemoryTokenStore:
    def __init__(self, secret: str = "client-secret") -> None:
        self.token = TikTokTokenData()
        self.secret = secret
        self.saved = []

    def load_token(self, token_key: str) -> TikTokTokenData:
        return self.token

    def save_token(self, token_key: str, token: TikTokTokenData) -> None:
        self.saved.append((token_key, token))
        self.token = token

    def delete_token(self, token_key: str) -> None:
        self.token = TikTokTokenData()

    def load_client_secret(self, token_key: str) -> str:
        return self.secret

    def save_client_secret(self, token_key: str, client_secret: str) -> None:
        self.secret = client_secret

    def delete_client_secret(self, token_key: str) -> None:
        self.secret = ""


def test_valid_token_is_reused_without_refresh(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TIKTOK_CLIENT_KEY", "client-key")
    store = MemoryTokenStore()
    store.token = TikTokTokenData(access_token="access", refresh_token="refresh", expires_at=200, refresh_expires_at=1000)
    service = TikTokOAuthService(tmp_path, token_store=store, time_provider=lambda: 100)

    assert service.get_access_token() == "access"


def test_refresh_rotates_saved_token(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TIKTOK_CLIENT_KEY", "client-key")
    store = MemoryTokenStore()
    store.token = TikTokTokenData(access_token="old", refresh_token="refresh", expires_at=10, refresh_expires_at=1000)

    def token_request(payload):
        assert payload["grant_type"] == "refresh_token"
        assert payload["client_secret"] == "client-secret"
        return {"access_token": "new", "refresh_token": "new-refresh", "expires_in": 100, "refresh_expires_in": 1000}

    service = TikTokOAuthService(tmp_path, token_store=store, token_request=token_request, time_provider=lambda: 100)

    assert service.get_access_token() == "new"
    assert store.token.refresh_token == "new-refresh"


def test_missing_client_secret_stops_without_plaintext_fallback(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TIKTOK_CLIENT_KEY", "client-key")
    store = MemoryTokenStore(secret="")
    store.token = TikTokTokenData(access_token="", refresh_token="refresh", expires_at=10, refresh_expires_at=1000)
    service = TikTokOAuthService(tmp_path, token_store=store, time_provider=lambda: 100)

    with pytest.raises(TikTokAuthError):
        service.get_access_token()


def test_keyring_unavailable_does_not_store_plaintext(monkeypatch) -> None:
    original_import = importlib.import_module

    def fail_import(name: str):
        if name == "keyring":
            raise ModuleNotFoundError("no keyring")
        return original_import(name)

    monkeypatch.setattr(importlib, "import_module", fail_import)
    store = TikTokKeyringStore()

    with pytest.raises(TikTokTokenStorageError):
        store.save_token("default", TikTokTokenData(access_token="access", refresh_token="refresh"))


def test_exchange_code_includes_pkce_and_does_not_require_project_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TIKTOK_CLIENT_KEY", "client-key")
    captured = {}

    def token_request(payload):
        captured.update(payload)
        return {"access_token": "access", "refresh_token": "refresh", "expires_in": 100, "refresh_expires_in": 1000}

    service = TikTokOAuthService(tmp_path, token_store=MemoryTokenStore(), token_request=token_request, time_provider=lambda: 100)

    token = service.exchange_code("code", "http://127.0.0.1:1234/callback/", "verifier", "client-secret")

    assert token.access_token == "access"
    assert captured["code_verifier"] == "verifier"
    assert captured["client_secret"] == "client-secret"
    assert "client_secret" not in os.environ
