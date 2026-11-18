from __future__ import annotations

import threading
import time

import requests

from src.shared.utils.env_load import VCOM_BASE_URL, VCOM_SENHA, VCOM_TENANT, VCOM_USUARIO


class VcomAuthProvider:
    _token: str | None = None
    _expires_at: float = 0
    _lock = threading.Lock()
    _ttl_seconds = 3600
    _refresh_margin_seconds = 120

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or VCOM_BASE_URL).rstrip("/")

    def obter_token(self, force_refresh: bool = False) -> str:
        with self._lock:
            if not force_refresh and self._token and time.time() < self._expires_at:
                return self._token

            response = requests.post(
                f"{self.base_url}/api/Autenticacao",
                json={
                    "Usuario": VCOM_USUARIO,
                    "Senha": VCOM_SENHA,
                    "Tenant": VCOM_TENANT,
                },
                timeout=30,
            )
            response.raise_for_status()

            token = response.text.strip().strip('"')
            if not token:
                try:
                    token = response.json()
                except ValueError:
                    token = ""

            if isinstance(token, dict):
                token = token.get("token") or token.get("Token") or token.get("access_token") or ""

            if not token:
                raise RuntimeError("VCOM nao retornou token de autenticacao.")

            self._token = str(token)
            self._expires_at = time.time() + self._ttl_seconds - self._refresh_margin_seconds
            return self._token

