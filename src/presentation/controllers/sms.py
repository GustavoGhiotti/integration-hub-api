import os
import time
from flask import Blueprint, request, jsonify
from src.application.services.sms_services import SmsService
from src.infrastructure.logging.logger_config import setup_logger, set_log_context

bp = Blueprint("sms", __name__, url_prefix="/sms")
log = setup_logger("sms_service", "sms.log")
service = SmsService()

DEBUG_LOGS = os.getenv("DEBUG_LOGS", "false").lower() == "true"

@bp.post("/callback")
def sms_callback():
    """
    Rota usada pela Sinch para enviar callbacks (delivery reports e respostas de clientes).
    Armazena o conteúdo bruto em TB_REGISTRO_SMS_RAW e atualiza TB_REGISTRO_SMS.
    """
    inicio = time.time()
    try:
        headers = dict(request.headers)
        raw_body = request.get_data(as_text=True)
        data = request.get_json(silent=True) or {}

        # Cria contexto adicional de log (reflete no log global)
        set_log_context(
            request_id=request.headers.get("X-Request-ID", "-"),
            user=data.get("identity", {}).get("endpoint", "-"),
            path=request.path,
            method=request.method,
            ip=request.remote_addr
        )

        # Extrai principais logs
        event = data.get("event", "-")
        msgid = data.get("id", "-")
        numero = data.get("identity", {}).get("endpoint", "-")

        # Executa processamenmto
        service.handle_callback(data, headers=headers, raw_body=raw_body)
        duracao = time.time() - inicio

        # Apenas logs resumidos
        log.info(
            f"SinchCallback | Evento={event} | MsgID={msgid} | Numero={numero} "
            f"| Status=OK | Tempo={duracao:.3f}s"
        )

        if DEBUG_LOGS:
            log.debug(f"Headers: {headers}")
            log.debug(f"Payload: {data}")

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        duracao = time.time() - inicio
        log.error(
            f"SinchCallback | Erro={e} | Tempo={duracao:.3f}s | "
            f"IP={request.remote_addr} | MsgID={data.get('id', '-')}"
        )
        return jsonify({"status": "erro", "detalhes": str(e)}), 500


@bp.get("/health")
def health():
    """Endpoint de verificação de saúde da rota SMS."""
    return jsonify({"status": "ok"}), 200