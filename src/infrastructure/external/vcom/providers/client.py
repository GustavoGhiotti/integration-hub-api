from __future__ import annotations

import json
import logging
import time
import traceback
from datetime import datetime, timezone
from typing import Any

import requests

from src.infrastructure.external.vcom.providers.auth import VcomAuthProvider
from src.infrastructure.logging.logger_config import get_log_context, setup_logger
from src.infrastructure.external.collectsys.method_logger import serialize_log_value
from src.shared.utils.env_load import VCOM_BASE_URL
from src.infrastructure.logging.api_audit import audit_trail


class VcomClient:
    def __init__(self, base_url: str | None = None, auth_provider: VcomAuthProvider | None = None):
        self.base_url = (base_url or VCOM_BASE_URL).rstrip("/")
        self.auth_provider = auth_provider or VcomAuthProvider(self.base_url)
        self.logger = setup_logger("vcom", "vcom.log")

    def get(self, path: str, **kwargs) -> Any:
        return self._request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> Any:
        return self._request("POST", path, **kwargs)

    def put(self, path: str, **kwargs) -> Any:
        return self._request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs) -> Any:
        return self._request("DELETE", path, **kwargs)

    def _request(
        self,
        method: str,
        path: str,
        retry_auth: bool = True,
        return_none_on_404: bool = True,
        **kwargs,
    ) -> Any:
        token = self.auth_provider.obter_token()
        headers = dict(kwargs.pop("headers", {}) or {})
        headers["Authorization"] = f"Bearer {token}"
        headers.setdefault("Content-Type", "application/json")

        url = f"{self.base_url}{path}"
        started_at = time.perf_counter()
        audit_started_at = datetime.now(timezone.utc)
        response = None
        audit_recorded = False
        attempt = 1

        def audit_response(current_response, current_started_at, current_attempt):
            try:
                response_data = current_response.json()
            except ValueError:
                response_data = None
            business_error = isinstance(response_data, dict) and any(
                response_data.get(key) is False for key in ("status", "success", "sucesso")
            )
            audit_trail.registrar_etapa(
                provider="VCOM", operation=path, started_at=current_started_at,
                request_payload={"params": kwargs.get("params"), "json": kwargs.get("json"), "data": kwargs.get("data")},
                response_payload=current_response.text, status_http=current_response.status_code,
                success=current_response.status_code < 400 and not business_error,
                business_error=business_error, method_http=method, endpoint=url,
                class_method=f"{type(self).__name__}._request", attempt=current_attempt,
                metadata={"headers": headers},
            )

        try:
            response = requests.request(method, url, headers=headers, timeout=45, **kwargs)
            if response.status_code == 401 and retry_auth:
                audit_response(response, audit_started_at, attempt)
                audit_recorded = True
                token = self.auth_provider.obter_token(force_refresh=True)
                headers["Authorization"] = f"Bearer {token}"
                attempt = 2
                audit_started_at = datetime.now(timezone.utc)
                audit_recorded = False
                response = requests.request(method, url, headers=headers, timeout=45, **kwargs)

            duration_ms = int((time.perf_counter() - started_at) * 1000)
            self.logger.log(
                logging.WARNING if response.status_code >= 400 else logging.INFO,
                "http_exchange %s",
                json.dumps(
                    {
                        "method": method,
                        "url": url,
                        "status_code": response.status_code,
                        "duration_ms": duration_ms,
                        "request": serialize_log_value(kwargs.get("json"), 4000),
                        "response": serialize_log_value(response.text, 4000),
                        "context": get_log_context(),
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            )
            audit_response(response, audit_started_at, attempt)
            audit_recorded = True

            if response.status_code == 404 and return_none_on_404:
                return None
            response.raise_for_status()

            if not response.text:
                return None

            try:
                return response.json()
            except ValueError:
                return response.text

        except Exception as exc:
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            self.logger.exception(
                "http_exception %s",
                json.dumps(
                    {
                        "method": method,
                        "url": url,
                        "duration_ms": duration_ms,
                        "exception_type": type(exc).__name__,
                        "exception_message": serialize_log_value(str(exc)),
                        "status_code": response.status_code if response is not None else None,
                        "response": serialize_log_value(response.text if response is not None else None),
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            )
            if not audit_recorded:
                audit_trail.registrar_etapa(
                    provider="VCOM", operation=path, started_at=audit_started_at,
                    request_payload={"params": kwargs.get("params"), "json": kwargs.get("json"), "data": kwargs.get("data")},
                    response_payload=response.text if response is not None else None,
                    status_http=response.status_code if response is not None else None, success=False,
                    method_http=method, endpoint=url, class_method=f"{type(self).__name__}._request",
                    attempt=attempt, metadata={"headers": headers}, exception=exc,
                    stack_trace=traceback.format_exc(),
                )
            raise

