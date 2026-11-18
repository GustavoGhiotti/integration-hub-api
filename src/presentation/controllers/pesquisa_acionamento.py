from flask import request, jsonify, current_app
from flask_smorest import Blueprint
from flask_jwt_extended import verify_jwt_in_request
from src.application.services.infobip_service import InfobipApi
from src.infrastructure.repositories.sql_acionamento_repository import (
    AcionamentoRepository,
    PortalAcordoRepository,
)
from src.presentation.schemas.auth import *

bp = Blueprint("Acionamento Whatsapp", __name__, url_prefix="/acionamento")


def _ok(data, message="ok", status=200):
    return jsonify({"success": True, "message": message, "data": data}), status


def _error(message, status=500):
    return jsonify({"success": False, "message": message}), status


def _required_args(*names):
    missing = [name for name in names if not (request.args.get(name) or "").strip()]
    if missing:
        return _error(f"parametros obrigatorios ausentes: {', '.join(missing)}", 400)
    return None


def _auth_guard():
    try:
        verify_jwt_in_request()
        return None
    except Exception:
        return _error("nao autorizado", 401)


@bp.get("/pesquisar")
def pesquisar_conversas():
    auth_error = _auth_guard()
    if auth_error:
        return auth_error

    validation = _required_args("DATA_ENVIO", "USUARIO")
    if validation:
        return validation

    numero_destino = request.args.get("NUMERO_DESTINO")
    numero_origem = request.args.get("NUMERO_ORIGEM")
    id_conversa = request.args.get("ID_CONVERSA")
    data_envio = request.args.get("DATA_ENVIO")
    usuario = request.args.get("USUARIO")

    try:
        service = AcionamentoRepository()
        dados = service.pesquisar(
            numero_destino, numero_origem, id_conversa, data_envio, usuario
        )

        if not dados:
            return _error("nenhuma conversa encontrada", 404)
        return _ok(dados)
    except Exception:
        current_app.logger.exception("Falha em /acionamento/pesquisar")
        return _error("erro interno", 500)


@bp.get("/salas")
def listar_salas_acionamento():
    auth_error = _auth_guard()
    if auth_error:
        return auth_error

    validation = _required_args("USUARIO")
    if validation:
        return validation

    numero_destino = request.args.get("NUMERO_DESTINO")
    numero_origem = request.args.get("NUMERO_ORIGEM")
    id_conversa = request.args.get("ID_CONVERSA")
    usuario = request.args.get("USUARIO")

    try:
        service = AcionamentoRepository()
        dados = service.salas(numero_destino, numero_origem, id_conversa, usuario)

        if not dados:
            return _error("nenhuma sala encontrada", 404)
        return _ok(dados)
    except Exception:
        current_app.logger.exception("Falha em /acionamento/salas")
        return _error("erro interno", 500)


@bp.get("/conversas")
def listar_conversas_portal_acordo():
    auth_error = _auth_guard()
    if auth_error:
        return auth_error

    validation = _required_args("FILA", "ATENDENTE", "DATA")
    if validation:
        return validation

    fila = request.args.get("FILA")
    atendente = request.args.get("ATENDENTE")
    data = request.args.get("DATA")

    try:
        service = PortalAcordoRepository()
        dados = service.salas(fila, data, atendente)

        if not dados:
            infobip_messages = InfobipApi.pegar_filas()
            return _error("nenhuma sala encontrada", 404)
        return _ok(dados)
    except Exception:
        current_app.logger.exception("Falha em /acionamento/conversas")
        return _error("erro interno", 500)


@bp.get("/atendentes")
def listar_atendentes_portal_acordo():
    auth_error = _auth_guard()
    if auth_error:
        return auth_error

    try:
        service = PortalAcordoRepository()
        dados = service.atendimento()
        if not dados:
            return _error("nenhum atendente encontrado", 404)
        return _ok(dados)
    except Exception:
        current_app.logger.exception("Falha em /acionamento/atendentes")
        return _error("erro interno", 500)


@bp.get("/mensagens")
def pesquisar_mensagens_portal_acordo():
    auth_error = _auth_guard()
    if auth_error:
        return auth_error

    validation = _required_args("ID_CONVERSA")
    if validation:
        return validation

    id_conversa = request.args.get("ID_CONVERSA")

    try:
        service = PortalAcordoRepository()
        dados = service.pesquisar(id_conversa)

        if not dados:
            return _error("nenhuma conversa encontrada", 404)
        return _ok(dados)
    except Exception:
        current_app.logger.exception("Falha em /acionamento/mensagens")
        return _error("erro interno", 500)


@bp.get("/infobip/pegar_filas")
def pegar_filas():
    auth_error = _auth_guard()
    if auth_error:
        return auth_error
    return InfobipApi.pegar_filas()
@bp.get("/infobip/pegar_agentes")
def pegar_agentes():
    auth_error = _auth_guard()
    if auth_error:
        return auth_error
    return InfobipApi.pegar_agentes()
@bp.get("/infobip/pegar_agentes_da_fila")
def pegar_agentes_da_fila():
    auth_error = _auth_guard()
    if auth_error:
        return auth_error
    queue_id = request.args.get("queue_id") or request.args.get("queueId") or request.args.get("FILA")
    if not queue_id:
        return _error("parametros obrigatorios ausentes: queue_id", 400)
    return InfobipApi.pegar_agentes_da_fila(queue_id)
@bp.get("/infobip/pegar_conversas")
def pegar_conversas():
    auth_error = _auth_guard()
    if auth_error:
        return auth_error
    fila = request.args.get("fila") or request.args.get("queueId") or request.args.get("FILA")
    atendente = request.args.get("atendente") or request.args.get("agentId") or request.args.get("ATENDENTE")
    status = request.args.get("status")
    data_inicio = request.args.get("data_inicio") or request.args.get("createdAtFrom")
    data_fim = request.args.get("data_fim") or request.args.get("createdAtTo")
    limit = request.args.get("limit") or request.args.get("pageSize") or request.args.get("size")
    return InfobipApi.pegar_conversas(fila, atendente, status, data_inicio, data_fim, limit)
@bp.get("/infobip/pegar_conversas_do_agente")
def pegar_conversas_do_agente():
    auth_error = _auth_guard()
    if auth_error:
        return auth_error
    agente_id = request.args.get("agente_id") or request.args.get("agentId") or request.args.get("ATENDENTE")
    if not agente_id:
        return _error("parametros obrigatorios ausentes: agente_id", 400)
    return InfobipApi.pegar_conversas_do_agente(agente_id)
@bp.get("/infobip/pegar_mensagens_da_conversa")
def pegar_mensagens_da_conversa():
    auth_error = _auth_guard()
    if auth_error:
        return auth_error
    conversation_id = request.args.get("conversation_id") or request.args.get("conversationId") or request.args.get("ID_CONVERSA")
    if not conversation_id:
        return _error("parametros obrigatorios ausentes: conversation_id", 400)
    return InfobipApi.pegar_mensagens_da_conversa(conversation_id)
