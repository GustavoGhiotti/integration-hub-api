import time
from datetime import datetime
from flask import Blueprint, request, jsonify
from src.infrastructure.logging.logger_config import setup_logger
from src.infrastructure.repositories.sql_email_event_repository import SqlEmailEventRepository

bp = Blueprint("sendgrid", __name__, url_prefix="/sendgrid")
repo = SqlEmailEventRepository()
log = setup_logger("sendgrid_webhook", "sendgrid.log", False)

# Guarda de tamanho do corpo (lote grande do SendGrid ainda cabe; evita abuso).
MAX_BODY = 5_000_000

# Se nada foi processado nos últimos N segundos E ainda há pendências, consideramos
# o consumidor (processo dedicado) parado -> /health responde 500 para alertar.
LIMITE_INATIVIDADE_SEG = 300


@bp.post("/webhook")
def webhook():
    """Ingestão: grava o corpo bruto na RAW o mais rápido possível e responde 200.
    O processamento pesado é feito por um PROCESSO DEDICADO (run_consumer.py),
    fora da API web — por isso este endpoint não conhece o consumidor."""
    inicio = time.time()

    raw = request.get_data(cache=False, as_text=True) or ""
    if len(raw) > MAX_BODY:
        raw = raw[:MAX_BODY]

    if not raw.strip():
        return jsonify({"ok": True, "recebido": 0}), 200

    try:
        headers = str(dict(request.headers))[:4000]
        repo.salvar_raw(headers, raw)
    except Exception as e:
        # Não conseguimos persistir -> devolve erro para o SendGrid reenviar depois.
        # Assim nenhum evento é perdido, mesmo com o banco momentaneamente fora.
        log.error("Falha ao gravar RAW: %s", e, exc_info=True)
        return jsonify({"ok": False, "error": "persist_failed"}), 503

    log.info(
        "WEBHOOK | Bytes=%d | IP=%s | Tempo=%.3fs",
        len(raw), request.remote_addr, time.time() - inicio,
    )
    return jsonify({"ok": True}), 200


@bp.get("/health")
def health():
    inicio = time.time()
    status = {"api": "ok"}
    consumidor_ok = False

    try:
        m = repo.metricas_saude()
        status["database"] = "ok"
        pendentes = m.get("pendentes") or 0
        status["raw_pendentes"] = m.get("pendentes")
        status["raw_processando"] = m.get("processando")
        status["raw_erros"] = m.get("erros")
        status["eventos_nao_agregados"] = m.get("eventos_nao_agregados")

        ultimo = m.get("ultimo_processamento")
        status["ultimo_processamento_utc"] = ultimo.isoformat() if ultimo else None

        # O consumidor roda em processo separado; a saúde é inferida pela atividade:
        # processou algo recentemente, OU não há nada pendente para processar.
        if ultimo is not None:
            idade = (datetime.utcnow() - ultimo).total_seconds()
            consumidor_ok = idade < LIMITE_INATIVIDADE_SEG or pendentes == 0
        else:
            consumidor_ok = pendentes == 0
        status["consumidor_processando"] = bool(consumidor_ok)
    except Exception as e:
        log.error("Healthcheck DB FAIL: %s", e, exc_info=True)
        status["database"] = "fail"

    duracao = time.time() - inicio
    log.info(
        "HEALTHCHECK | DB=%s | Pendentes=%s | Processando=%s | Tempo=%.3fs",
        status.get("database"), status.get("raw_pendentes"),
        status.get("consumidor_processando"), duracao,
    )

    ok = status.get("database") == "ok" and consumidor_ok
    return jsonify(status), (200 if ok else 500)
