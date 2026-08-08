from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from services.youtube.models import YouTubeAuthError
from services.youtube.token_store import KeyringTokenStore


YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube"


class YouTubeOAuthService:
    def __init__(
        self,
        base_dir: Path,
        token_store: KeyringTokenStore | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.base_dir = base_dir
        self.token_store = token_store or KeyringTokenStore()
        self.logger = logger or logging.getLogger("ai_video_factory.youtube")

    def get_credentials(self):
        self._load_env()
        project_id = self._google_project_id()
        client_config = self._client_config()
        refresh_token = self.token_store.get_refresh_token(project_id)
        if refresh_token:
            credentials = self._credentials_from_refresh_token(client_config, refresh_token)
            try:
                if credentials.expired and credentials.refresh_token:
                    self.logger.info("token refresh started project_id=%s", project_id)
                    from google.auth.transport.requests import Request

                    credentials.refresh(Request())
                    self.logger.info("token refresh success project_id=%s", project_id)
            except Exception as exc:
                self.logger.warning("token refresh failed project_id=%s error=%s", project_id, self._safe_error(exc))
                raise YouTubeAuthError("YouTube認証トークンの更新に失敗しました。再認証してください。") from exc
            return credentials

        self.logger.info("oauth started project_id=%s", project_id)
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow

            secrets_file = self._client_secrets_file()
            flow = InstalledAppFlow.from_client_secrets_file(str(secrets_file), scopes=[YOUTUBE_UPLOAD_SCOPE])
            credentials = flow.run_local_server(port=0, prompt="consent")
        except Exception as exc:
            self.logger.warning("oauth failed project_id=%s error=%s", project_id, self._safe_error(exc))
            raise YouTubeAuthError("YouTube OAuth認証に失敗しました。") from exc
        if not credentials.refresh_token:
            raise YouTubeAuthError("YouTube OAuth認証でrefresh tokenを取得できませんでした。")
        self.token_store.save_refresh_token(project_id, credentials.refresh_token)
        self.logger.info("oauth success project_id=%s", project_id)
        return credentials

    def build_youtube_client(self):
        credentials = self.get_credentials()
        try:
            from googleapiclient.discovery import build
        except Exception as exc:
            raise YouTubeAuthError("YouTube Data API client libraryを読み込めません。") from exc
        return build("youtube", "v3", credentials=credentials)

    def _load_env(self) -> None:
        try:
            from dotenv import load_dotenv

            load_dotenv(self.base_dir / ".env")
        except Exception:
            pass

    def _client_secrets_file(self) -> Path:
        raw = os.environ.get("YOUTUBE_CLIENT_SECRETS_FILE", "").strip()
        if not raw:
            raise YouTubeAuthError(".envにYOUTUBE_CLIENT_SECRETS_FILEを設定してください。")
        path = Path(raw)
        if not path.is_absolute():
            path = self.base_dir / path
        if not path.exists():
            raise YouTubeAuthError("YouTube OAuth client secretファイルが見つかりません。")
        return path

    def _client_config(self) -> dict[str, object]:
        try:
            data = json.loads(self._client_secrets_file().read_text(encoding="utf-8"))
        except Exception as exc:
            raise YouTubeAuthError("YouTube OAuth client secretファイルを読み込めません。") from exc
        if "installed" in data and isinstance(data["installed"], dict):
            return data["installed"]
        if "web" in data and isinstance(data["web"], dict):
            return data["web"]
        raise YouTubeAuthError("YouTube OAuth client secretファイルの形式が正しくありません。")

    def _credentials_from_refresh_token(self, client_config: dict[str, object], refresh_token: str):
        try:
            from google.oauth2.credentials import Credentials
        except Exception as exc:
            raise YouTubeAuthError("Google OAuth credentials libraryを読み込めません。") from exc
        return Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri=str(client_config.get("token_uri") or "https://oauth2.googleapis.com/token"),
            client_id=str(client_config.get("client_id") or ""),
            client_secret=str(client_config.get("client_secret") or ""),
            scopes=[YOUTUBE_UPLOAD_SCOPE],
        )

    def _google_project_id(self) -> str:
        configured = os.environ.get("YOUTUBE_TOKEN_KEY", "").strip()
        if configured:
            return configured
        try:
            return str(self._client_config().get("project_id") or "default")
        except YouTubeAuthError:
            return "default"

    def _safe_error(self, exc: Exception) -> str:
        return exc.__class__.__name__
