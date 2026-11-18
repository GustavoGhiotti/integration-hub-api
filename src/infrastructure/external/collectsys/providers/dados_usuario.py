import json
import logging
import time
import traceback
from datetime import datetime, timezone

import requests
from src.infrastructure.database.sql_server_connection import SQLServerConnection
from src.infrastructure.repositories.sql_collectsys_repository import SqlCollectSysRepository
from src.shared.utils.env_load import get_env_required
from src.domain.entities.usuario_collectsys import UsuarioCollectSys
from flask import g
from typing import cast

from .method_logger import (
    build_instance_context,
    get_collectsys_method_logger,
    serialize_log_value,
)
from src.infrastructure.logging.api_audit import audit_trail


class DadosUsuario:
    def __init__(self): 
        self.key_api = get_env_required("TOKEN_DB_API")
        self.db = SQLServerConnection(server=get_env_required("DB_65"), database="easycollector")
        self.usuario_cedente()
        self.url = self.gerar_url_servidor()

    def _get_method_logger(self, method_name: str):
        return get_collectsys_method_logger(self, method_name)

    def _post_soap(
        self,
        *,
        method_name: str,
        url: str,
        body: str,
        headers: dict[str, str],
        stream: bool = False,
        response_transform=None,
        extra_context: dict | None = None,
    ):
        logger = self._get_method_logger(method_name)
        started_at = time.perf_counter()
        audit_started_at = datetime.now(timezone.utc)
        response = None
        raw_response = None

        request_payload = {
            "method": method_name,
            "url": url,
            "headers": headers,
            "request_len": len(body or ""),
            "request_preview": serialize_log_value(body, 4000),
            "context": build_instance_context(self),
        }
        if extra_context:
            request_payload["extra_context"] = extra_context

        try:
            response = requests.post(
                url=url,
                data=body,
                headers=headers,
                verify=False,
                stream=stream,
            )
            raw_response = response.text
            result = response_transform(raw_response) if response_transform else raw_response

            duration_ms = int((time.perf_counter() - started_at) * 1000)
            response_payload = {
                "method": method_name,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "has_retorno_erro": isinstance(result, str) and "<RetornoErro>" in result,
                "response_len": len(result or "") if isinstance(result, str) else None,
                "response_preview": serialize_log_value(result, 4000),
            }
            if extra_context:
                response_payload["extra_context"] = extra_context

            exchange_payload = {**request_payload, **response_payload}
            level = logging.INFO
            if response.status_code >= 500 or response_payload["has_retorno_erro"]:
                level = logging.WARNING

            logger.log(level, "http_exchange %s", json.dumps(exchange_payload, ensure_ascii=False, default=str))
            context = build_instance_context(self)
            audit_trail.registrar_etapa(
                provider="COLLECTSYS", operation=method_name, started_at=audit_started_at,
                request_payload=body, response_payload=result, status_http=response.status_code,
                success=response.status_code < 400 and not response_payload["has_retorno_erro"],
                business_error=response_payload["has_retorno_erro"], method_http="POST",
                endpoint=url, class_method=f"{type(self).__name__}.{method_name}",
                attempt=(extra_context or {}).get("tentativa", 1),
                metadata={"headers": headers, "context": context, "extra_context": extra_context},
                dimensions={"id_cedente": context.get("id_cedente")},
            )
            return result

        except Exception as exc:
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            error_payload = {
                "method": method_name,
                "duration_ms": duration_ms,
                "exception_type": type(exc).__name__,
                "exception_message": serialize_log_value(str(exc)),
                "request_body": serialize_log_value(body),
            }

            if response is not None:
                error_payload["status_code"] = response.status_code
            if raw_response is not None:
                error_payload["response"] = serialize_log_value(raw_response)
            if extra_context:
                error_payload["extra_context"] = extra_context

            logger.exception(
                "http_exception %s",
                json.dumps(error_payload, ensure_ascii=False, default=str),
            )
            context = build_instance_context(self)
            audit_trail.registrar_etapa(
                provider="COLLECTSYS", operation=method_name, started_at=audit_started_at,
                request_payload=body, response_payload=raw_response,
                status_http=response.status_code if response is not None else None, success=False,
                method_http="POST", endpoint=url, class_method=f"{type(self).__name__}.{method_name}",
                attempt=(extra_context or {}).get("tentativa", 1),
                metadata={"headers": headers, "context": context, "extra_context": extra_context},
                exception=exc, stack_trace=traceback.format_exc(),
                dimensions={"id_cedente": context.get("id_cedente")},
            )
            raise

