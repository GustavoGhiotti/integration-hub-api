from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.infrastructure.logging.audit_sanitizer import extract_dimensions, sanitize_payload
from src.infrastructure.logging.audit_spool import AuditSpool
from src.infrastructure.logging.logger_config import get_log_context
from src.infrastructure.repositories.sql_api_audit_repository import SqlApiAuditRepository


logger = logging.getLogger("api_audit")


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "sim", "on"}


class ApiAuditTrail:
    """Auditoria fail-open: falhas do LOGS_ROBOS nunca interrompem a API."""

    def __init__(self):
        self.enabled = os.getenv("API_AUDIT_ENABLED", "1").lower() not in {"0", "false", "no"}
        # False mantem a auditoria em arquivos locais, sem criar conexao ou
        # enviar eventos ao banco LOGS_ROBOS.
        self.database_enabled = _env_bool("API_AUDIT_DATABASE_ENABLED", True)
        # Cada evento leva o ambiente no proprio envelope do spool. Assim, mesmo
        # apos restart ou troca de configuracao, ele chega ao schema correto.
        self.homologacao = _env_bool("HOMOLOGACAO", False)
        self.max_payload = int(os.getenv("API_AUDIT_MAX_PAYLOAD_BYTES", "65536"))
        self.flush_interval = max(0.25, float(os.getenv("API_AUDIT_FLUSH_INTERVAL_SECONDS", "3")))
        self.max_backoff = max(self.flush_interval, float(os.getenv("API_AUDIT_MAX_BACKOFF_SECONDS", "60")))
        self._lock = threading.Lock()
        self._states: dict[str, dict[str, Any]] = {}
        self._repository_instance = None
        self._spool_instance = None
        self._local_spool_instance = None
        self._stop_event = threading.Event()
        self._worker_started = False

    def start(self):
        if not self.enabled or not self.database_enabled or self._worker_started:
            return
        with self._lock:
            if self._worker_started:
                return
            self._spool()
            threading.Thread(target=self._consume, name="api-audit-writer", daemon=True).start()
            self._worker_started = True

    def _repository(self):
        if self._repository_instance is None:
            self._repository_instance = SqlApiAuditRepository()
        return self._repository_instance

    def _spool(self):
        if self._spool_instance is None:
            fsync = os.getenv("API_AUDIT_SPOOL_FSYNC", "0").lower() in {"1", "true", "yes"}
            self._spool_instance = AuditSpool(fsync=fsync)
        return self._spool_instance

    def _local_spool(self):
        if self._local_spool_instance is None:
            default_dir = Path(__file__).resolve().parents[3] / "logs" / "auditoria_local"
            directory = os.getenv("API_AUDIT_LOCAL_DIR") or str(default_dir)
            fsync = _env_bool("API_AUDIT_SPOOL_FSYNC", False)
            self._local_spool_instance = AuditSpool(directory=directory, fsync=fsync)
        return self._local_spool_instance

    def _rotate_local_if_needed(self):
        spool = self._local_spool()
        max_bytes = max(1, int(os.getenv("API_AUDIT_LOCAL_MAX_BYTES", "10000000")))
        backup_count = max(1, int(os.getenv("API_AUDIT_LOCAL_BACKUP_COUNT", "10")))
        try:
            if spool.active_path.exists() and spool.active_path.stat().st_size >= max_bytes:
                spool.rotate()
            ready_files = spool.ready_files()
            for expired_path in ready_files[:-backup_count]:
                expired_path.unlink(missing_ok=True)
        except OSError:
            logger.exception("Falha ao rotacionar auditoria local")

    def _consume(self):
        failures = 0
        last_recovery = 0.0
        try:
            self._spool().recover_stale()
            last_recovery = time.monotonic()
        except Exception:
            logger.exception("Falha ao recuperar arquivos antigos do spool de auditoria")

        while not self._stop_event.is_set():
            if time.monotonic() - last_recovery >= 60:
                try:
                    self._spool().recover_stale()
                except Exception:
                    logger.exception("Falha ao recuperar arquivos abandonados do spool")
                last_recovery = time.monotonic()
            try:
                self._spool().rotate()
            except Exception:
                logger.exception("Falha ao rotacionar spool de auditoria")

            try:
                ready_files = self._spool().ready_files()
            except Exception:
                failures += 1
                logger.exception("Falha ao listar lotes do spool de auditoria")
                ready_files = []

            cycle_failures = 0
            for ready_path in ready_files:
                processing_path = self._spool().claim(ready_path)
                if processing_path is None:
                    continue
                try:
                    events = self._spool().read(processing_path)
                    self._repository().processar_lote(events)
                    self._spool().complete(processing_path)
                    failures = 0
                except ValueError:
                    failures = 0
                    invalid_path = self._spool().quarantine(processing_path)
                    logger.exception("Lote de auditoria invalido movido para %s", invalid_path.name)
                    continue
                except Exception:
                    failures += 1
                    cycle_failures += 1
                    try:
                        self._spool().release(processing_path)
                    except Exception:
                        logger.exception("Falha ao devolver lote de auditoria para retry")
                    if cycle_failures == 1:
                        logger.exception(
                            "Falha ao processar lote de auditoria; lote preservado para retry e fila continuara"
                        )
                    else:
                        logger.debug(
                            "Falha adicional no spool de auditoria: %s",
                            ready_path.name,
                        )

            if cycle_failures > 1:
                logger.warning(
                    "Ciclo do spool concluido com %s lotes pendentes; eventos foram preservados",
                    cycle_failures,
                )

            delay = min(self.max_backoff, self.flush_interval * (2 ** min(failures, 6)))
            self._stop_event.wait(delay)

    def _append(self, operation: str, execution_id: str, data: dict):
        try:
            spool = self._spool() if self.database_enabled else self._local_spool()
            written = spool.append(
                operation,
                execution_id,
                data,
                homologacao=self.homologacao,
            )
        except Exception:
            logger.exception(
                "Falha ao gravar spool local de auditoria; fluxo da API foi preservado ID_EXECUCAO=%s",
                execution_id,
            )
            return False
        if not self.database_enabled:
            self._rotate_local_if_needed()
            return written
        try:
            self.start()
        except Exception:
            # O evento ja esta duravel e sera recuperado no proximo start.
            logger.exception("Falha ao iniciar consumidor do spool de auditoria")
        return written

    def iniciar(self, data: dict) -> bool:
        if not self.enabled:
            return False
        execution_id = str(data["ID_EXECUCAO"])
        if not self._append("iniciar", execution_id, data):
            return False
        with self._lock:
            self._states[execution_id] = {"providers": set(), "last_error": None, "order": 0}
        return True

    def is_active(self, execution_id: str | None = None) -> bool:
        execution_id = execution_id or get_log_context().get("execution_id")
        with self._lock:
            return bool(execution_id and str(execution_id) in self._states)

    def state(self, execution_id: str) -> dict[str, Any]:
        with self._lock:
            state = self._states.get(str(execution_id), {})
            return {**state, "providers": set(state.get("providers", set()))}

    def registrar_etapa(self, **kwargs):
        try:
            return self._registrar_etapa(**kwargs)
        except Exception:
            logger.exception(
                "Falha ao registrar etapa de auditoria; fluxo principal foi preservado"
            )
            return None

    def _registrar_etapa(
        self,
        *,
        provider: str,
        operation: str,
        started_at: datetime,
        request_payload: Any = None,
        response_payload: Any = None,
        status_http: int | None = None,
        success: bool | None = None,
        business_error: bool = False,
        method_http: str | None = None,
        endpoint: str | None = None,
        class_method: str | None = None,
        attempt: int = 1,
        metadata: Any = None,
        exception: Exception | None = None,
        stack_trace: str | None = None,
        execution_id: str | None = None,
        dimensions: dict | None = None,
    ):
        execution_id = str(execution_id or get_log_context().get("execution_id") or "")
        if not execution_id or not self.is_active(execution_id):
            return
        ended_at = datetime.now(timezone.utc)
        sent = sanitize_payload(request_payload, self.max_payload)
        received = sanitize_payload(response_payload, self.max_payload)
        meta = sanitize_payload(metadata, min(self.max_payload, 16000))
        explicit_dimensions = {key: value for key, value in (dimensions or {}).items() if value is not None}
        dimensions = {**extract_dimensions(request_payload, response_payload, metadata), **explicit_dimensions}
        provider = provider.upper()
        try:
            attempt = int(attempt)
        except (TypeError, ValueError):
            attempt = 1

        with self._lock:
            state = self._states.get(execution_id)
            if not state:
                return
            state["providers"].add(provider)
            state["order"] += 1
            order = state["order"]
            if exception or business_error or success is False or (status_http is not None and status_http >= 400):
                state["last_error"] = {
                    "origin": provider,
                    "stage": operation,
                    "type": type(exception).__name__ if exception else None,
                    "message": str(exception) if exception else None,
                }

        response_raw = received.text or ""
        safe_exception = sanitize_payload(str(exception), 4000).text if exception else None
        data = {
            "ID_EXECUCAO": execution_id, "ID_ETAPA_PAI": None, "ORDEM": order, "TENTATIVA": attempt,
            "TIPO_ETAPA": "EXTERNA", "PROVEDOR": provider, "OPERACAO": operation,
            "CLASSE_METODO": class_method, "METODO_HTTP": method_http, "ENDPOINT_EXTERNO": endpoint,
            "ID_CLIENTE": dimensions.get("id_cliente"), "ID_CEDENTE": dimensions.get("id_cedente"),
            "NOME_CEDENTE": dimensions.get("nome_cedente"), "ID_CONTRATO": dimensions.get("id_contrato"),
            "ID_ACORDO": dimensions.get("id_acordo"), "DT_INICIO_UTC": started_at,
            "DT_FIM_UTC": ended_at, "DURACAO_MS": max(0, int((ended_at - started_at).total_seconds() * 1000)),
            "SUCESSO": success, "STATUS_HTTP_EXTERNO": status_http, "RETORNO_ERRO_NEGOCIO": business_error,
            "PAYLOAD_ENVIO": sent.text, "PAYLOAD_RETORNO": received.text,
            "TAMANHO_ENVIO_BYTES": sent.original_size, "TAMANHO_RETORNO_BYTES": received.original_size,
            "HASH_RETORNO": hashlib.sha256(response_raw.encode("utf-8")).digest() if response_raw else None,
            "PAYLOAD_TRUNCADO": sent.truncated or received.truncated, "TIPO_EXCECAO": type(exception).__name__ if exception else None,
            "MENSAGEM_ERRO": safe_exception, "STACK_TRACE": sanitize_payload(stack_trace, self.max_payload).text,
            "METADADOS_JSON": meta.text,
        }
        self._append("registrar_etapa", execution_id, data)

    def finalizar(self, execution_id: str, data: dict):
        if self.is_active(execution_id):
            self._append("finalizar", execution_id, data)
            with self._lock:
                self._states.pop(str(execution_id), None)


audit_trail = ApiAuditTrail()


def flow_from_providers(providers: set[str]) -> str:
    relevant = providers & {"COLLECTSYS", "VCOM"}
    if relevant == {"COLLECTSYS", "VCOM"}:
        return "MISTO"
    return next(iter(relevant), "PADRAO")
