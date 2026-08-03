from __future__ import annotations

import importlib
import json
from dataclasses import asdict, dataclass

from services.tiktok.models import TikTokTokenData, TikTokTokenStorageError


@dataclass(frozen=True)
class TikTokKeyringStore:
    service_name: str = "AI Video Factory TikTok"

    def _keyring(self):
        try:
            return importlib.import_module("keyring")
        except Exception as exc:
            raise TikTokTokenStorageError(
                "Windows Credential Managerを利用できないため、TikTok認証情報を安全に保存できません。"
            ) from exc

    def _token_username(self, token_key: str) -> str:
        return f"tiktok-oauth-token:{token_key}"

    def _secret_username(self, token_key: str) -> str:
        return f"tiktok-client-secret:{token_key}"

    def load_token(self, token_key: str) -> TikTokTokenData:
        keyring = self._keyring()
        try:
            raw = keyring.get_password(self.service_name, self._token_username(token_key))
        except Exception as exc:
            raise TikTokTokenStorageError("TikTok認証情報をWindows Credential Managerから読み込めませんでした。") from exc
        if not raw:
            return TikTokTokenData()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise TikTokTokenStorageError("TikTok認証情報の保存形式が正しくありません。再接続してください。") from exc
        return TikTokTokenData(
            access_token=str(data.get("access_token") or ""),
            refresh_token=str(data.get("refresh_token") or ""),
            expires_at=int(data.get("expires_at") or 0),
            refresh_expires_at=int(data.get("refresh_expires_at") or 0),
            open_id=str(data.get("open_id") or ""),
            scope=str(data.get("scope") or ""),
            token_type=str(data.get("token_type") or "Bearer"),
        )

    def save_token(self, token_key: str, token: TikTokTokenData) -> None:
        if not token.access_token or not token.refresh_token:
            raise TikTokTokenStorageError("TikTok認証で必要なtokenを取得できませんでした。")
        keyring = self._keyring()
        try:
            keyring.set_password(self.service_name, self._token_username(token_key), json.dumps(asdict(token)))
        except Exception as exc:
            raise TikTokTokenStorageError("TikTok認証情報をWindows Credential Managerへ保存できませんでした。") from exc

    def delete_token(self, token_key: str) -> None:
        self._delete(self._token_username(token_key))

    def load_client_secret(self, token_key: str) -> str:
        keyring = self._keyring()
        try:
            return keyring.get_password(self.service_name, self._secret_username(token_key)) or ""
        except Exception as exc:
            raise TikTokTokenStorageError("TikTok client secretをWindows Credential Managerから読み込めませんでした。") from exc

    def save_client_secret(self, token_key: str, client_secret: str) -> None:
        if not client_secret:
            raise TikTokTokenStorageError("TikTok client secretが空です。")
        keyring = self._keyring()
        try:
            keyring.set_password(self.service_name, self._secret_username(token_key), client_secret)
        except Exception as exc:
            raise TikTokTokenStorageError("TikTok client secretをWindows Credential Managerへ保存できませんでした。") from exc

    def delete_client_secret(self, token_key: str) -> None:
        self._delete(self._secret_username(token_key))

    def _delete(self, username: str) -> None:
        keyring = self._keyring()
        try:
            keyring.delete_password(self.service_name, username)
        except Exception:
            return
