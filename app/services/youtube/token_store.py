from __future__ import annotations

import importlib
from dataclasses import dataclass

from services.youtube.models import YouTubeTokenStorageError


@dataclass(frozen=True)
class KeyringTokenStore:
    service_name: str = "AI Video Factory YouTube"

    def _keyring(self):
        try:
            return importlib.import_module("keyring")
        except Exception as exc:
            raise YouTubeTokenStorageError(
                "Windows Credential Managerを利用できないため、YouTube認証トークンを安全に保存できません。"
            ) from exc

    def _username(self, project_id: str) -> str:
        return f"youtube-refresh-token:{project_id}"

    def get_refresh_token(self, project_id: str) -> str:
        keyring = self._keyring()
        try:
            token = keyring.get_password(self.service_name, self._username(project_id))
        except Exception as exc:
            raise YouTubeTokenStorageError(
                "Windows Credential ManagerからYouTube認証トークンを読み込めませんでした。"
            ) from exc
        return token or ""

    def save_refresh_token(self, project_id: str, refresh_token: str) -> None:
        if not refresh_token:
            raise YouTubeTokenStorageError("YouTube認証のrefresh tokenが取得できませんでした。")
        keyring = self._keyring()
        try:
            keyring.set_password(self.service_name, self._username(project_id), refresh_token)
        except Exception as exc:
            raise YouTubeTokenStorageError(
                "Windows Credential ManagerへYouTube認証トークンを安全に保存できませんでした。"
            ) from exc

    def delete_refresh_token(self, project_id: str) -> None:
        keyring = self._keyring()
        try:
            keyring.delete_password(self.service_name, self._username(project_id))
        except Exception:
            return
