import os
import time
from flask import Blueprint, jsonify, request
from src.infrastructure.queue.config_queue import sms_queue
from src.infrastructure.logging.logger_config import setup_logger, set_log_context
from src.domain.utils.parser_infobip import *
from src.infrastructure.security.auth_decorator import token_require

bp = Blueprint("infobip", __name__, url_prefix="/infobip")
log = setup_logger("infobip_webhook", "infobip.log")

DEBUG_LOGS = os.getenv("DEBUG_LOGS", "false").lower() == "true"

@bp.post("/webhook")
def webhook_sms():
    inicio = time.time()
    try:
        headers = dict(request.headers)
        raw_body = request.get_data(as_text=True)
        data = request.get_json(silent=True)

        set_log_context(
            request_id=request.headers.get("X-Request-ID", "-"),
            user=headers.get("X-User", "-"),
            path=request.path,
            method=request.method,
            ip=request.remote_addr
        )

        if not data:
            log.warning(
                "InfobipWebhook | JSON ausente | Bytes=%s | IP=%s",
                len(raw_body or ""),
                request.remote_addr,
            )
            return jsonify({"error": "JSON ausente"}), 400

        results = data.get("results") or []
        if not results:
            log.info(
                "InfobipWebhook | Sem resultados | Bytes=%s | IP=%s",
                len(raw_body or ""),
                request.remote_addr,
            )
            return jsonify({"sucesso": True}), 200

        for msg in results:

            job = {
                "id_msg": msg.get("messageId"),
                "enviado_para": msg.get("destination") or msg.get("to"),
                "from_number": msg.get("from"),
                "hora_envio": parse_infobip_datetime(msg.get("sentAt")),
                "entrega_msg": parse_infobip_datetime(msg.get("doneAt")),
                "status": msg.get("status", {}).get("groupName"),
                "status_desc": msg.get("status", {}).get("description"),
                "sms_count": msg.get("smsCount"),

                "valor_sms": (
                    f"{msg.get('price', {}).get('pricePerMessage')} "
                    f"{msg.get('price', {}).get('currency')}"
                    if msg.get("price") else None
                ),
                "erro": None if msg.get("error", {}).get("name") == "NO_ERROR"
                        else msg.get("error", {}).get("name"),
                "raw_json": msg,
            }

            sms_queue.put(job)

        ids = [m.get("messageId") for m in results if m.get("messageId")]
        duracao = time.time() - inicio
        log.info(
            "InfobipWebhook | Results=%s | Ids=%s | IP=%s | Tempo=%.3fs",
            len(results),
            ids[:3],
            request.remote_addr,
            duracao,
        )

        if DEBUG_LOGS:
            log.debug("Headers: %s", headers)
            log.debug("Payload: %s", data)

        return jsonify({"sucesso": True}), 200

    except Exception as e:
        duracao = time.time() - inicio
        log.error(
            "InfobipWebhook | Erro=%s | Tempo=%.3fs | IP=%s",
            e,
            duracao,
            request.remote_addr,
            exc_info=True,
        )
        return jsonify({"error": str(e)}), 500

@bp.post("/webhook/inbound")
def webhook_inbound():
    inicio = time.time()
    try:
        headers = dict(request.headers)
        raw_body = request.get_data(as_text=True)
        data = request.get_json(silent=True)

        set_log_context(
            request_id=request.headers.get("X-Request-ID", "-"),
            user=headers.get("X-User", "-"),
            path=request.path,
            method=request.method,
            ip=request.remote_addr
        )

        if not data:
            log.warning(
                "InfobipInbound | JSON ausente | Bytes=%s | IP=%s",
                len(raw_body or ""),
                request.remote_addr,
            )
            return jsonify({"error": "JSON ausente"}), 400

        results = data.get("results") or data.get("messages") or []
        if not results:
            log.info(
                "InfobipInbound | Sem resultados | Bytes=%s | IP=%s",
                len(raw_body or ""),
                request.remote_addr,
            )
            return jsonify({"sucesso": True}), 200

        for msg in results:
            job = {
                "id_msg": msg.get("messageId") or msg.get("message_id"),
                "enviado_para": msg.get("destination") or msg.get("to") or msg.get("from"),
                "from_number": msg.get("from"),
                "hora_envio": parse_infobip_datetime(msg.get("receivedAt") or msg.get("sentAt")),
                "entrega_msg": None,
                "status": "INBOUND",
                "status_desc": "INBOUND_MESSAGE",
                "sms_count": msg.get("smsCount"),
                "valor_sms": None,
                "erro": None,
                "raw_json": msg,
            }

            sms_queue.put(job)

        ids = [m.get("messageId") for m in results if m.get("messageId")]
        duracao = time.time() - inicio
        log.info(
            "InfobipInbound | Results=%s | Ids=%s | IP=%s | Tempo=%.3fs",
            len(results),
            ids[:3],
            request.remote_addr,
            duracao,
        )

        if DEBUG_LOGS:
            log.debug("Headers: %s", headers)
            log.debug("Payload: %s", data)

        return jsonify({"sucesso": True}), 200

    except Exception as e:
        duracao = time.time() - inicio
        log.error(
            "InfobipInbound | Erro=%s | Tempo=%.3fs | IP=%s",
            e,
            duracao,
            request.remote_addr,
            exc_info=True,
        )
        return jsonify({"error": str(e)}), 500


@bp.get("/health")
def health():
    return jsonify({"status": "ok"}), 200
