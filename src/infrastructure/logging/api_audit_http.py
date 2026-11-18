from __future__ import annotations

import json
import os
import socket
import traceback
from datetime import datetime, timezone
from urllib.parse import urlsplit

from flask import g, got_request_exception, request

from src.infrastructure.logging.api_audit import audit_trail, flow_from_providers
from src.infrastructure.logging.audit_sanitizer import extract_dimensions, sanitize_payload
from src.infrastructure.logging.logger_config import get_log_context


# /sendgrid é webhook de altíssimo volume: auditar cada evento reintroduziria
# o gargalo (parse do corpo + escrita em disco sob lock global) que o redesenho
# eliminou. Ele já tem rastreabilidade própria (tabela RAW + log sendgrid.log).
_SKIP_PREFIXES = ("/docs", "/openapi.json", "/redoc", "/favicon", "/src/static", "/sendgrid")


def _should_audit() -> bool:
    return request.path != "/" and not request.path.startswith(_SKIP_PREFIXES)


def _request_origin() -> str | None:
    value = request.headers.get("Origin") or request.headers.get("Referer")
    if not value:
        return None
    parsed = urlsplit(value)
    return f"{parsed.scheme}://{parsed.netloc}"[:100] if parsed.scheme and parsed.netloc else value.split("?", 1)[0][:100]


def classify_response(status_code: int, body, exception=None) -> tuple[bool, str, str | None, str | None]:
    business_failure = isinstance(body, dict) and any(
        body.get(key) is False for key in ("status", "success", "sucesso")
    )
    if exception:
        return False, "ERRO_INTERNO" if status_code >= 500 else "ERRO_TRATADO", "API", type(exception).__name__
    if status_code >= 500:
        return False, "ERRO_INTERNO", "API", None
    if status_code >= 400:
        return False, "ERRO_TRATADO", "API", None
    if business_failure:
        return False, "ERRO_NEGOCIO", "NEGOCIO", None
    return True, "SUCESSO", None, None


def register_api_audit(app):
    @app.before_request
    def start_api_audit():
        if not _should_audit():
            return
        try:
            now = datetime.now(timezone.utc)
            body = request.get_json(silent=True)
            if body is None:
                form_data = request.form.to_dict(flat=False)
                file_data = {
                    key: {
                        "nome": item.filename,
                        "content_type": item.content_type,
                        "content_length": item.content_length,
                    }
                    for key, item in request.files.items()
                }
                body = ({"campos": form_data, "uploads": file_data} if form_data or file_data else request.get_data(cache=True)) or None
            query = request.args.to_dict(flat=False)
            route_params = request.view_args or {}
            headers = dict(request.headers)
            dimensions = extract_dimensions(body, query, route_params, headers)
            payload = sanitize_payload(body, audit_trail.max_payload)
            safe_headers = sanitize_payload(headers, 16000)
            safe_query = sanitize_payload(query, 16000)
            safe_route = sanitize_payload(route_params, 16000)
            safe_keys = sanitize_payload({k: v for k, v in dimensions.items() if k != "documento_hash"}, 16000)
            context = get_log_context()
            forwarded_for = request.headers.get("X-Forwarded-For", "")
            client_ip = forwarded_for.split(",")[0].strip() if forwarded_for else request.remote_addr
            data = {
                "ID_EXECUCAO": request.id, "REQUEST_ID": request.id,
                "CORRELATION_ID": request.headers.get("X-Correlation-ID"), "DT_INICIO_UTC": now,
                "METODO_HTTP": request.method, "ROTA": request.path, "ENDPOINT": request.endpoint,
                "CONTENT_TYPE": request.content_type, "QUERY_STRING": safe_query.text[:4000] if safe_query.text else None,
                "PARAMETROS_ROTA_JSON": safe_route.text, "HEADERS_JSON": safe_headers.text,
                "PAYLOAD_ENTRADA": payload.text, "TAMANHO_ENTRADA_BYTES": payload.original_size,
                "PAYLOAD_TRUNCADO": payload.truncated, "FLUXO": "PADRAO",
                "ID_CLIENTE": dimensions.get("id_cliente"), "ID_CEDENTE": dimensions.get("id_cedente"),
                "NOME_CEDENTE": dimensions.get("nome_cedente"), "ID_CONTRATO": dimensions.get("id_contrato"),
                "ID_ACORDO": dimensions.get("id_acordo"), "DOCUMENTO_HASH": dimensions.get("documento_hash"),
                "DOCUMENTO_MASCARADO": dimensions.get("documento_mascarado"), "TELEFONE_FINAL": dimensions.get("telefone_final"),
                "CHAVES_BUSCA_JSON": safe_keys.text, "ID_USUARIO": context.get("user_id"), "USUARIO": None,
                "TIPO_AUTENTICACAO": "BEARER" if request.headers.get("Authorization") else None,
                "IP_CLIENTE": client_ip, "USER_AGENT": request.user_agent.string[:1000],
                "ORIGEM_CHAMADA": _request_origin(),
                "AMBIENTE": os.getenv("AMBIENTE", os.getenv("FLASK_ENV", "producao")),
                "NOME_APLICACAO": "APISistemaAcme", "VERSAO_APLICACAO": os.getenv("APP_VERSION"),
                "HOST_APLICACAO": socket.gethostname(), "PROCESSO_APLICACAO": os.getpid(),
            }
            g.api_audit_started = audit_trail.iniciar(data)
            g.api_audit_start_utc = now
            g.api_audit_dimensions = dimensions
        except Exception:
            app.logger.exception("Falha ao preparar auditoria; requisicao seguira normalmente")
            g.api_audit_started = False

    def capture_exception(sender, exception, **extra):
        if sender is app and getattr(g, "api_audit_started", False):
            g.api_audit_exception = exception
            g.api_audit_stack = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))

    got_request_exception.connect(capture_exception, app, weak=False)

    @app.after_request
    def finish_api_audit(response):
        if not getattr(g, "api_audit_started", False):
            return response
        try:
            ended_at = datetime.now(timezone.utc)
            raw_body = response.get_json(silent=True)
            if raw_body is None:
                raw_body = response.get_data(as_text=True)
            safe_response = sanitize_payload(raw_body, audit_trail.max_payload)
            exception = getattr(g, "api_audit_exception", None)
            success, status_process, origin, exception_type = classify_response(response.status_code, raw_body, exception)
            state = audit_trail.state(request.id)
            last_error = state.get("last_error") or {}
            if not success and last_error:
                origin = last_error.get("origin") or origin
                exception_type = exception_type or last_error.get("type")
            final_error = last_error if not success else {}
            context = get_log_context()
            dimensions = {**getattr(g, "api_audit_dimensions", {}), **extract_dimensions(raw_body)}
            message = None
            if isinstance(raw_body, dict):
                message = raw_body.get("message") or raw_body.get("mensagem") or raw_body.get("error")
            data = {
                "ID_EXECUCAO": request.id, "DT_FIM_UTC": ended_at,
                "DURACAO_MS": max(0, int((ended_at - g.api_audit_start_utc).total_seconds() * 1000)),
                "ID_USUARIO": context.get("user_id"),
                "USUARIO": context.get("user") if context.get("auth_type") else None,
                "TIPO_AUTENTICACAO": context.get("auth_type"),
                "FLUXO": flow_from_providers(state.get("providers", set())), "ID_CLIENTE": dimensions.get("id_cliente"),
                "ID_CEDENTE": dimensions.get("id_cedente"), "NOME_CEDENTE": dimensions.get("nome_cedente"),
                "ID_CONTRATO": dimensions.get("id_contrato"), "ID_ACORDO": dimensions.get("id_acordo"),
                "SUCESSO": success, "STATUS_PROCESSO": status_process, "STATUS_HTTP": response.status_code,
                "ORIGEM_ERRO": origin if not success else None,
                "ETAPA_ERRO": final_error.get("stage"), "CODIGO_ERRO": None,
                "RETORNO_USUARIO": safe_response.text, "TAMANHO_RETORNO_BYTES": safe_response.original_size,
                "PAYLOAD_TRUNCADO": safe_response.truncated,
                "TIPO_EXCECAO": exception_type if not success else None,
                "MENSAGEM_ERRO": (
                    str(exception or message or final_error.get("message") or "")[:4000] or None
                ) if not success else None,
                "STACK_TRACE": (
                    sanitize_payload(getattr(g, "api_audit_stack", None), audit_trail.max_payload).text
                ) if not success else None,
            }
            audit_trail.finalizar(request.id, data)
        except Exception:
            app.logger.exception("Falha ao finalizar auditoria; resposta foi preservada")
        return response
