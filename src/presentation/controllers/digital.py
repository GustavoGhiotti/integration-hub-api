from flask import jsonify
from flask_jwt_extended import get_jwt, get_jwt_identity
from flask_smorest import Blueprint
from src.presentation.schemas.digital import *
from src.presentation.schemas import Erro401Schema
from src.infrastructure.security.auth_decorator import token_require
from src.shared.utils.validador import validate_input
from src.application.services.twilio_service import *
from src.application.services.infobip_whatsapp_service import (
    InfobipEnvioService,
    InfobipTemplateService,
)


bp = Blueprint("Acme Digital", __name__, url_prefix="/digital")


def _obter_solicitante_autenticado() -> dict:
    claims = get_jwt()
    id_usuario = int(get_jwt_identity())
    return {
        "id": id_usuario,
        "usuario": claims.get("usuario") or str(id_usuario),
    }

@bp.post("/twilio/template")
@token_require("/digital")
@bp.doc(
    security=[{"BearerAuth": []}],
    description="Obtém informações de um template Twilio, incluindo variáveis necessárias para envio.",
    summary="Informações do template Twilio",
    tags=["Acme Digital"]
)
@bp.arguments(TwilioTemplateRequestSchema, location="json")
@bp.response(200, TwilioTemplateResponseSchema)
@bp.response(401, Erro401Schema)
def obter_info_template(body: TwilioTemplateRequestSchema):

    template = TwilioTemplateService().obter_dados_template(body.sidTemplate)

    return jsonify({"status":True, "necessarioTemplate": template}), 200


@bp.post("/infobip/template")
@token_require("/digital")
@bp.doc(
    security=[{"BearerAuth": []}],
    description="obtem informacoes de um template Infobip, incluindo variaveis necessarias para envio.",
    summary="informacoes do template Infobip",
    tags=["Acme Digital"]
)
@bp.arguments(InfobipTemplateRequestSchema, location="json")
@bp.response(200, TwilioTemplateResponseSchema)
@bp.response(401, Erro401Schema)
def obter_info_template_infobip(body: InfobipTemplateRequestSchema):
    template = InfobipTemplateService().obter_dados_template(body.nomeTemplate)

    return jsonify({"status": True, "necessarioTemplate": template}), 200


@bp.post("/twilio/envio-mensagens-whatsapp")
@bp.doc(
    security=[{"BearerAuth": []}],
    description="Envia mensagens via WhatsApp usando um template Twilio.",
    summary="Envio de mensagens (WhatsApp)",
    tags=["Acme Digital"]
)
@bp.arguments(EnvioMensagemSchema, location="json")
@bp.response(200, EnvioMensagemResponseSchema)
@bp.response(401, Erro401Schema)
@token_require("/digital")
def envio_boleto_whatsapp(dados: EnvioMensagemSchema):
    resultado = TwilioEnvioService().enviar(
        dados.telefoneCliente,
        dados.idCedente,
        dados.canal,
        dados.sidTemplate,
        dados.variaveis,
        _obter_solicitante_autenticado(),
    )
    
    return jsonify({"status":True}, resultado), 200


@bp.post("/infobip/envio-mensagens-whatsapp")
@bp.doc(
    security=[{"BearerAuth": []}],
    description="Envia mensagens via WhatsApp usando um template Infobip.",
    summary="Envio de mensagens (WhatsApp)",
    tags=["Acme Digital"]
)
@bp.arguments(EnvioMensagemSchema, location="json")
@bp.response(200, EnvioMensagemResponseSchema)
@bp.response(401, Erro401Schema)
@token_require("/digital")
def envio_boleto_whatsapp(dados: EnvioMensagemSchema):
    resultado = InfobipEnvioService().enviar(dados.telefoneCliente,
        dados.idCedente,
        dados.canal,
        dados.sidTemplate,
        dados.variaveis or {},
        _obter_solicitante_autenticado(),
    )

    return jsonify({"status": True}, resultado), 200
