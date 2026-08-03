from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import socket
import time
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Callable

from services.tiktok.models import TikTokAuthError, TikTokTokenData
from services.tiktok.token_store import TikTokKeyringStore


TIKTOK_AUTHORIZE_URL = "https://www.tiktok.com/v2/auth/authorize/"
TIKTOK_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
TIKTOK_UPLOAD_SCOPE = "video.upload"


class TikTokOAuthService:
    def __init__(
        self,
        base_dir: Path,
        token_store: TikTokKeyringStore | None = None,
        logger: logging.Logger | None = None,
        browser_open: Callable[[str], bool] | None = None,
        token_request: Callable[[dict[str, str]], dict[str, object]] | None = None,
        time_provider: Callable[[], float] = time.time,
    ) -> None:
        self.base_dir = base_dir
        self.token_store = token_store or TikTokKeyringStore()
        self.logger = logger or logging.getLogger("ai_video_factory.tiktok")
        self.browser_open = browser_open or webbrowser.open
        self.token_request = token_request or self._token_request
        self.time_provider = time_provider

    def has_token(self) -> bool:
        token = self.token_store.load_token(self._token_key())
        return bool(token.access_token or token.refresh_token)

    def save_client_secret(self, client_secret: str) -> None:
        self.token_store.save_client_secret(self._token_key(), client_secret)

    def disconnect(self) -> None:
        token_key = self._token_key()
        self.token_store.delete_token(token_key)
        self.token_store.delete_client_secret(token_key)
        self.logger.info("local disconnect completed token_key=%s", token_key)

    def get_access_token(self) -> str:
        token_key = self._token_key()
        token = self.token_store.load_token(token_key)
        now = int(self.time_provider())
        if token.access_token and token.expires_at - 60 > now:
            return token.access_token
        if token.refresh_token:
            self.logger.info("token refresh started token_key=%s", token_key)
            refreshed = self.refresh_token(token.refresh_token)
            self.token_store.save_token(token_key, refreshed)
            self.logger.info("token refresh success token_key=%s", token_key)
            return refreshed.access_token
        raise TikTokAuthError("TikTokに接続されていません。先にConnect TikTokを実行してください。")

    def start_oauth_flow(self, callback_timeout_seconds: int = 180) -> TikTokTokenData:
        self._load_env()
        client_key = self._client_key()
        client_secret = self._client_secret_required()
        redirect_uri = self._redirect_uri()
        state = secrets.token_urlsafe(32)
        code_verifier = secrets.token_urlsafe(64)[:128]
        code_challenge = hashlib.sha256(code_verifier.encode("utf-8")).hexdigest()

        self.logger.info("oauth started token_key=%s", self._token_key())
        callback = _OAuthCallbackServer(redirect_uri, state, callback_timeout_seconds)
        try:
            actual_redirect_uri = callback.redirect_uri
            params = {
                "client_key": client_key,
                "scope": TIKTOK_UPLOAD_SCOPE,
                "response_type": "code",
                "redirect_uri": actual_redirect_uri,
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
            self.browser_open(f"{TIKTOK_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}")
            code = callback.wait_for_code()
        finally:
            callback.close()
        token = self.exchange_code(code, actual_redirect_uri, code_verifier, client_secret)
        self.token_store.save_token(self._token_key(), token)
        self.logger.info("oauth success token_key=%s", self._token_key())
        return token

    def exchange_code(self, code: str, redirect_uri: str, code_verifier: str, client_secret: str | None = None) -> TikTokTokenData:
        if not code:
            raise TikTokAuthError("TikTok OAuthのauthorization codeを取得できませんでした。")
        payload = {
            "client_key": self._client_key(),
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        }
        if client_secret:
            payload["client_secret"] = client_secret
        try:
            response = self.token_request(payload)
        except TikTokAuthError:
            raise
        except Exception as exc:
            self.logger.warning("oauth failed token_key=%s error=%s", self._token_key(), self._safe_error(exc))
            raise TikTokAuthError("TikTok OAuth token交換に失敗しました。") from exc
        return self._token_from_response(response)

    def refresh_token(self, refresh_token: str) -> TikTokTokenData:
        client_secret = self._client_secret_required()
        payload = {
            "client_key": self._client_key(),
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        try:
            response = self.token_request(payload)
        except TikTokAuthError:
            raise
        except Exception as exc:
            self.logger.warning("token refresh failed token_key=%s error=%s", self._token_key(), self._safe_error(exc))
            raise TikTokAuthError("TikTok tokenの更新に失敗しました。再接続してください。") from exc
        return self._token_from_response(response)

    def _token_request(self, payload: dict[str, str]) -> dict[str, object]:
        data = urllib.parse.urlencode(payload).encode("utf-8")
        request = urllib.request.Request(
            TIKTOK_TOKEN_URL,
            data=data,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise TikTokAuthError("TikTok OAuth APIへの接続に失敗しました。") from exc

    def _token_from_response(self, response: dict[str, object]) -> TikTokTokenData:
        if not isinstance(response, dict):
            raise TikTokAuthError("TikTok OAuth APIの応答形式が正しくありません。")
        if response.get("error"):
            error = response.get("error")
            error_code = str(error.get("code") or error.get("error") or "oauth_error") if isinstance(error, dict) else str(error)
            raise TikTokAuthError("TikTok OAuth認証に失敗しました。", error_code=error_code)
        access_token = str(response.get("access_token") or "")
        refresh_token = str(response.get("refresh_token") or "")
        if not access_token or not refresh_token:
            raise TikTokAuthError("TikTok OAuth APIの応答にtokenが含まれていません。")
        now = int(self.time_provider())
        expires_in = int(response.get("expires_in") or 0)
        refresh_expires_in = int(response.get("refresh_expires_in") or 0)
        return TikTokTokenData(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=now + expires_in,
            refresh_expires_at=now + refresh_expires_in,
            open_id=str(response.get("open_id") or ""),
            scope=str(response.get("scope") or ""),
            token_type=str(response.get("token_type") or "Bearer"),
        )

    def _load_env(self) -> None:
        try:
            from dotenv import load_dotenv

            load_dotenv(self.base_dir / ".env")
        except Exception:
            pass

    def _client_key(self) -> str:
        self._load_env()
        client_key = os.environ.get("TIKTOK_CLIENT_KEY", "").strip()
        if not client_key:
            raise TikTokAuthError(".envにTIKTOK_CLIENT_KEYを設定してください。")
        return client_key

    def _token_key(self) -> str:
        self._load_env()
        return os.environ.get("TIKTOK_TOKEN_KEY", "").strip() or self._client_key()

    def _client_secret_required(self) -> str:
        client_secret = self.token_store.load_client_secret(self._token_key())
        if not client_secret:
            raise TikTokAuthError("TikTok client secretが安全に保存されていません。Connect TikTok前に登録してください。")
        return client_secret

    def _redirect_uri(self) -> str:
        self._load_env()
        return os.environ.get("TIKTOK_REDIRECT_URI", "http://127.0.0.1:*/callback/").strip()

    def _safe_error(self, exc: Exception) -> str:
        return exc.__class__.__name__


class _OAuthCallbackServer:
    def __init__(self, redirect_uri_template: str, expected_state: str, timeout_seconds: int) -> None:
        parsed = urllib.parse.urlparse(redirect_uri_template)
        if parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise TikTokAuthError("TikTok OAuthのredirect URIは127.0.0.1またはlocalhostを使用してください。")
        port = self._resolve_port(self._configured_port(parsed.netloc))
        path = parsed.path or "/callback/"
        self.redirect_uri = urllib.parse.urlunparse((parsed.scheme or "http", f"{parsed.hostname}:{port}", path, "", "", ""))
        self.expected_state = expected_state
        self.timeout_seconds = timeout_seconds
        self.code = ""
        self.error = ""
        self.httpd = HTTPServer((parsed.hostname or "127.0.0.1", port), self._handler_class())
        self.httpd.timeout = 0.5

    def wait_for_code(self) -> str:
        deadline = time.time() + self.timeout_seconds
        while time.time() < deadline and not self.code and not self.error:
            self.httpd.handle_request()
        if self.error:
            raise TikTokAuthError(self.error)
        if not self.code:
            raise TikTokAuthError("TikTok OAuth callbackがタイムアウトしました。")
        return self.code

    def close(self) -> None:
        self.httpd.server_close()

    def _resolve_port(self, configured_port: int | None) -> int:
        if configured_port:
            return configured_port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    def _configured_port(self, netloc: str) -> int | None:
        if ":" not in netloc:
            return None
        port_text = netloc.rsplit(":", 1)[1]
        if port_text == "*":
            return None
        try:
            return int(port_text)
        except ValueError as exc:
            raise TikTokAuthError("TikTok OAuthのredirect URIのportが正しくありません。") from exc

    def _handler_class(self):
        parent = self

        class OAuthHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                state = query.get("state", [""])[0]
                code = query.get("code", [""])[0]
                error = query.get("error", [""])[0]
                if state != parent.expected_state:
                    parent.error = "TikTok OAuthのstateが一致しません。認証を中止しました。"
                    self._respond("Authentication failed. You can close this window.")
                    return
                if error:
                    parent.error = "TikTok OAuth認証が拒否されました。"
                    self._respond("Authentication failed. You can close this window.")
                    return
                parent.code = code
                self._respond("Authentication completed. You can close this window.")

            def log_message(self, _format: str, *_args) -> None:
                return

            def _respond(self, body: str) -> None:
                encoded = body.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

        return OAuthHandler
