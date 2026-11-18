import uuid
import hmac
from requests import RequestException
from flask import Blueprint, jsonify, request
from src.application.services.webhook_meta_service import WebhookMetaService
from src.infrastructure.logging.logger_config import set_log_context, setup_logger
from src.shared.utils.env_load import *


bp = Blueprint("webhook_meta", __name__)

log = setup_logger("webhook_meta", "webhook_meta.log")
LIMITE_BYTES_WEBHOOK_META = 1_048_576
MODO_SUBSCRIBE_META = "subscribe"


def _contar_eventos_meta(payload: dict) -> tuple[int, int, int]:
    entradas = payload.get("entry") or []
    quantidade_mensagens = 0
    quantidade_status = 0

    for entrada in entradas:
        for alteracao in (entrada.get("changes") or []):
            valor = (alteracao or {}).get("value") or {}
            quantidade_mensagens += len(valor.get("messages") or [])
            quantidade_status += len(valor.get("statuses") or [])

    return len(entradas), quantidade_mensagens, quantidade_status


def _obter_request_id() -> str:
    request_id = (request.headers.get("X-Request-ID") or "").strip()
    return request_id or str(uuid.uuid4())


def _configurar_contexto_log(request_id: str) -> None:
    set_log_context(
        request_id=request_id,
        path=request.path,
        method=request.method,
        ip=request.headers.get("X-Forwarded-For", request.remote_addr),
    )

def _validar_token_api_interna(req) -> bool:
    token_esperado = (API_SISTEMA_ACME_INTERNAL_TOKEN or "").strip()
    token_recebido = (req.headers.get("X-Internal-Token", "") or "").strip()

    if not token_esperado or not token_recebido:
        return False
    
    return hmac.compare_digest(token_recebido, token_esperado)

@bp.before_request
def validar_endpoints_internos_templates():
    if not request.path.startswith("/monitoria-whatsapp/api/whatsapp/templates"):
        return None
    
    request_id = _obter_request_id()
    _configurar_contexto_log(request_id)

    token_configurado = (API_SISTEMA_ACME_INTERNAL_TOKEN or "").strip()
    
    if not token_configurado:
        log.error("Endpoint interno de templates indisponivel: token interno nao configurado")
        return jsonify({"erro": "API interna indisponivel", "request_id": request_id}), 500

    if not _validar_token_api_interna(request):
        log.warning("Endpoint interno de templates rejeitado: token interno invalido")
        return jsonify({"erro": "Acesso interno invalido", "request_id": request_id}), 403
    
    return None

# =========================================================
# TEMPLATE
# =========================================================

@bp.get("/webhook/meta")
def verificar_webhook_meta():
    request_id = _obter_request_id()
    _configurar_contexto_log(request_id)
    service = WebhookMetaService()

    if not service.verify_token:
        log.error("Webhook Meta rejeitado: META_VERIFY_TOKEN nao configurado")
        return jsonify({"erro": "Webhook indisponivel", "request_id": request_id}), 500

    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode != MODO_SUBSCRIBE_META:
        log.warning("Tentativa de verificacao do webhook Meta com modo invalido mode=%s", mode)
        return jsonify({"erro": "Modo de verificacao invalido", "request_id": request_id}), 400

    if service.validar_token_verificacao(token):
        log.info("Verificacao do webhook Meta concluida com sucesso")
        return challenge or "", 200

    log.warning("Tentativa de verificacao do webhook Meta com token invalido")
    return jsonify({"erro": "Token invalido", "request_id": request_id}), 403


@bp.post("/webhook/meta")
def receber_webhook_meta():
    request_id = _obter_request_id()
    _configurar_contexto_log(request_id)
    service = WebhookMetaService()
    corpo_bruto = request.get_data(cache=True)

    if not service.app_secret:
        log.error("Webhook Meta rejeitado: META_APP_SECRET nao configurado")
        return jsonify({"erro": "Webhook indisponivel", "request_id": request_id}), 500

    if len(corpo_bruto) > LIMITE_BYTES_WEBHOOK_META:
        log.warning("Webhook Meta rejeitado por tamanho excedido bytes=%s", len(corpo_bruto))
        return jsonify({"erro": "Payload excede limite permitido", "request_id": request_id}), 413

    assinatura = request.headers.get("X-Hub-Signature-256")
    if not service.validar_assinatura_meta(corpo_bruto, assinatura):
        log.warning("Webhook Meta rejeitado: assinatura invalida")
        return jsonify({"erro": "Assinatura Meta invalida", "request_id": request_id}), 403

    payload = request.get_json(silent=True)
    if payload is None or not isinstance(payload, dict):
        log.warning("Webhook Meta rejeitado: JSON invalido")
        return jsonify({"erro": "JSON invalido", "request_id": request_id}), 400

    quantidade_entradas, quantidade_mensagens, quantidade_status = _contar_eventos_meta(payload)

    templates_processados = 0
    if service.possui_eventos_template(payload):
        try:
            resultado_templates = service.processar_eventos_template_meta(payload)
            templates_processados = resultado_templates["eventos_processados"]
        except Exception as exc:
            log.error("Falha ao processar webhook de templates da Meta: %s", exc, exc_info=True)
            return jsonify({"erro": "Falha ao processar webhook de templates", "request_id": request_id}), 500

    if quantidade_mensagens == 0 and quantidade_status == 0:
        log.info(
            "Webhook Meta processado localmente somente para templates entradas=%s templates=%s",
            quantidade_entradas,
            templates_processados,
        )
        return jsonify({
            "ok": True,
            "request_id": request_id,
            "entradas": quantidade_entradas,
            "mensagens": quantidade_mensagens,
            "status": quantidade_status,
            "templates_processados": templates_processados,
            "encaminhado_copilot": False,
        }), 200

    if not service.target_url:
        log.error("Webhook Meta rejeitado: COPILOT_META_WEBHOOK_URL nao configurado")
        return jsonify({"erro": "Webhook indisponivel", "request_id": request_id}), 500

    if not service.internal_token:
        log.error("Webhook Meta rejeitado: COPILOT_META_WEBHOOK_TOKEN nao configurado")
        return jsonify({"erro": "Webhook indisponivel", "request_id": request_id}), 500

    try:
        resposta = service.encaminhar(
            corpo_bruto,
            dict(request.headers),
            request_id=request_id,
        )
    except RequestException as exc:
        log.error(
            "Falha ao encaminhar webhook Meta para o Copilot: %s",
            exc,
            exc_info=True,
        )
        return jsonify({"erro": "Falha ao encaminhar webhook", "request_id": request_id}), 502

    corpo_resposta = (resposta.text or "")[:1000]

    if resposta.status_code >= 500:
        log.error(
            "Copilot indisponivel ao receber webhook Meta status=%s body=%s",
            resposta.status_code,
            corpo_resposta,
        )
        return jsonify({"erro": "Servico interno indisponivel", "request_id": request_id}), 502

    if resposta.status_code >= 400:
        log.error(
            "Copilot rejeitou webhook Meta status=%s body=%s",
            resposta.status_code,
            corpo_resposta,
        )
        return jsonify({"erro": "Servico interno rejeitou webhook", "request_id": request_id}), 502

    log.info(
        "Webhook Meta processado com sucesso entradas=%s mensagens=%s status=%s templates=%s status_copilot=%s",
        quantidade_entradas,
        quantidade_mensagens,
        quantidade_status,
        templates_processados,
        resposta.status_code,
    )
    return jsonify({
        "ok": True,
        "request_id": request_id,
        "status_copilot": resposta.status_code,
        "entradas": quantidade_entradas,
        "mensagens": quantidade_mensagens,
        "status": quantidade_status,
        "templates_processados": templates_processados,
        "encaminhado_copilot": True,
    }), 200


# =========================================================
# TEMPLATE
# =========================================================

@bp.post("/api/whatsapp/templates")
def criar_template_whatsapp():
    request_id = _obter_request_id()
    _configurar_contexto_log(request_id)
    service = WebhookMetaService()

    payload = request.get_json(silent=True)
    if payload is None or not isinstance(payload, dict):
        return jsonify({"erro": "JSON invalido", "request_id": request_id}), 400

    try:
        resultado = service.criar_template_local(payload)
        return jsonify({
            "ok": True,
            "request_id": request_id,
            **resultado,
        }), 201

    except ValueError as exc:
        return jsonify({"erro": str(exc), "request_id": request_id}), 400

    except Exception as exc:
        log.error("Falha ao criar template local: %s", exc, exc_info=True)
        return jsonify({"erro": "Falha ao criar template", "request_id": request_id}), 500


@bp.put("/api/whatsapp/templates/<int:id_template>")
def atualizar_template_whatsapp(id_template: int):
    request_id = _obter_request_id()
    _configurar_contexto_log(request_id)
    service = WebhookMetaService()

    payload = request.get_json(silent=True)
    if payload is None or not isinstance(payload, dict):
        return jsonify({"erro": "JSON invalido", "request_id": request_id}), 400

    try:
        resultado = service.atualizar_template_rascunho(id_template, payload)
        return jsonify({
            "ok": True,
            "request_id": request_id,
            **resultado,
        }), 200

    except ValueError as exc:
        return jsonify({"erro": str(exc), "request_id": request_id}), 400

    except Exception as exc:
        log.error("Falha ao atualizar template %s: %s", id_template, exc, exc_info=True)
        return jsonify({"erro": "Falha ao atualizar template", "request_id": request_id}), 500


@bp.delete("/api/whatsapp/templates/<int:id_template>")
def excluir_template_whatsapp(id_template: int):
    request_id = _obter_request_id()
    _configurar_contexto_log(request_id)
    service = WebhookMetaService()

    usuario_responsavel = (
        request.headers.get("X-Usuario-Responsavel")
        or request.args.get("usuario_responsavel")
    )

    try:
        resultado = service.excluir_template_rascunho(
            id_template,
            usuario_responsavel=usuario_responsavel,
        )
        return jsonify({
            "ok": True,
            "request_id": request_id,
            **resultado,
        }), 200

    except ValueError as exc:
        return jsonify({"erro": str(exc), "request_id": request_id}), 400

    except Exception as exc:
        log.error("Falha ao excluir template %s: %s", id_template, exc, exc_info=True)
        return jsonify({"erro": "Falha ao excluir template", "request_id": request_id}), 500


@bp.get("/api/whatsapp/templates")
def listar_templates_whatsapp():
    request_id = _obter_request_id()
    _configurar_contexto_log(request_id)
    service = WebhookMetaService()

    filtro = (request.args.get("filtro") or "").strip().lower() or None

    try:
        templates = service.listar_templates(filtro=filtro)
        return jsonify({
            "ok": True,
            "request_id": request_id,
            "total": len(templates),
            "templates": templates,
        }), 200

    except Exception as exc:
        log.error("Falha ao listar templates: %s", exc, exc_info=True)
        return jsonify({"erro": "Falha ao listar templates", "request_id": request_id}), 500
    
@bp.get("/api/whatsapp/templates/ativos")
def listar_templates_ativos_whatsapp():
    request_id = _obter_request_id()
    _configurar_contexto_log(request_id)
    service = WebhookMetaService()

    try:
        templates = service.listar_templates_ativos_operacionais()
        return jsonify({
            "ok": True,
            "request_id": request_id,
            "total": len(templates),
            "templates": templates,
        }), 200

    except Exception as exc:
        log.error("Falha ao listar templates ativos: %s", exc, exc_info=True)
        return jsonify({"erro": "Falha ao listar templates ativos", "request_id": request_id}), 500
    
@bp.patch("/api/whatsapp/templates/<int:id_template>/ativo")
def atualizar_ativo_template_whatsapp(id_template: int):
    request_id = _obter_request_id()
    _configurar_contexto_log(request_id)
    service = WebhookMetaService()

    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"erro": "JSON invalido", "request_id": request_id}), 400

    if "ativo" not in payload or not isinstance(payload.get("ativo"), bool):
        return jsonify({"erro": "Campo 'ativo' obrigatorio e deve ser booleano.", "request_id": request_id}), 400

    usuario_responsavel = (
        payload.get("usuario_responsavel")
        or request.headers.get("X-Usuario-Responsavel")
    )

    try:
        resultado = service.atualizar_ativo_template(
            id_template,
            ativo=payload["ativo"],
            usuario_responsavel=usuario_responsavel,
        )
        return jsonify({
            "ok": True,
            "request_id": request_id,
            **resultado,
        }), 200

    except ValueError as exc:
        return jsonify({"erro": str(exc), "request_id": request_id}), 400

    except Exception as exc:
        log.error("Falha ao atualizar ativo do template %s: %s", id_template, exc, exc_info=True)
        return jsonify({"erro": "Falha ao atualizar disponibilidade do template", "request_id": request_id}), 500


@bp.post("/api/whatsapp/templates/<int:id_template>/submeter-meta")
def submeter_template_whatsapp_meta(id_template: int):
    request_id = _obter_request_id()
    _configurar_contexto_log(request_id)
    service = WebhookMetaService()

    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"erro": "JSON invalido", "request_id": request_id}), 400

    usuario_responsavel = (
        payload.get("usuario_responsavel")
        or request.headers.get("X-Usuario-Responsavel")
    )

    try:
        resultado = service.submeter_template_meta(
            id_template,
            usuario_responsavel=usuario_responsavel,
        )
        return jsonify({
            "ok": True,
            "request_id": request_id,
            **resultado,
        }), 200

    except ValueError as exc:
        return jsonify({"erro": str(exc), "request_id": request_id}), 400

    except RuntimeError as exc:
        log.error("Falha na submissao do template %s para Meta: %s", id_template, exc, exc_info=True)
        return jsonify({"erro": str(exc), "request_id": request_id}), 502

    except Exception as exc:
        log.error("Falha inesperada ao submeter template %s para Meta: %s", id_template, exc, exc_info=True)
        return jsonify({"erro": "Falha ao submeter template para Meta", "request_id": request_id}), 500


@bp.get("/api/whatsapp/templates/<int:id_template>")
def detalhar_template_whatsapp(id_template: int):
    request_id = _obter_request_id()
    _configurar_contexto_log(request_id)
    service = WebhookMetaService()

    try:
        template = service.obter_template(id_template)
        if not template:
            return jsonify({"erro": "Template nao encontrado", "request_id": request_id}), 404

        return jsonify({
            "ok": True,
            "request_id": request_id,
            "template": template,
        }), 200

    except Exception as exc:
        log.error("Falha ao detalhar template %s: %s", id_template, exc, exc_info=True)
        return jsonify({"erro": "Falha ao detalhar template", "request_id": request_id}), 500
