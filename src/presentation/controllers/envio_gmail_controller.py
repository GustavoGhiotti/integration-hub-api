from typing import Any

from flask import jsonify, request
from flask_smorest import Blueprint
from marshmallow import ValidationError
from werkzeug.datastructures import FileStorage

from src.application.services.envio_email_service import ChamadoEnvioEmailService
from src.infrastructure.security.auth_decorator import token_require
from src.presentation.schemas.envio_email_schema import (
    EnviarEmailResponseSchema,
    EnviarEmailSchema,
    ErroValidacaoEmailSchema,
)
import asyncio

from src.application.services.google_chat_service import (
    GoogleChatService,
)
from src.domain.exceptions.google_chat_exception import (
    ChatInativoError,
    ChatNaoEncontradoError,
    ChatWebhookNaoConfiguradoError,
    GoogleChatSendError,
    IdentificacaoChatInvalidaError,
)
from src.infrastructure.external.gmail.gmail_chat_sender import (
    GmailChatSender,
)
from src.infrastructure.repositories.sql_google_chat_repository import (
    GoogleChatRepository,
)
from src.presentation.schemas.google_chat_schema import (
    EnviarMensagemGoogleChatResponseSchema,
    EnviarMensagemGoogleChatSchema,
    ErroGoogleChatSchema,
)




bp = Blueprint("Gmail", __name__, url_prefix="/gmail",)


@bp.post("/email/enviar")
@bp.doc(
    security=[{"BearerAuth": []}],
    summary="Enviar e-mail",
    description=(
        "Envia um e-mail em texto simples. "
        "Aceita application/json para mensagens sem anexo "
        "e multipart/form-data para mensagens com anexo."
    ),
    tags=["E-mails"],
)
@bp.response(
    200,
    EnviarEmailResponseSchema,
    description="E-mail enviado com sucesso.",
)
@bp.response(
    400,
    ErroValidacaoEmailSchema,
    description="Dados da requisição inválidos.",
)
@token_require("/emails")
def enviar_email():
    schema = EnviarEmailSchema()

    try:
        dados_requisicao = _obter_dados_requisicao()
        dados_validados = schema.load(dados_requisicao)
    except ValidationError as erro:
        return jsonify(
            {
                "success": False,
                "message": "Dados inválidos.",
                "errors": erro.messages,
            }
        ), 400

    service = ChamadoEnvioEmailService()
    resultado = service.enviar(dados_validados)

    identificador_mensagem = (
        resultado.identificadores_mensagem[0]
    )

    return jsonify(
        {
            "success": True,
            "message": "E-mail enviado com sucesso.",
            "data": {
                "messageId": identificador_mensagem,
            },
        }
    ), 200



def _obter_dados_requisicao() -> dict[str, Any]:
    if request.is_json:
        conteudo_json = request.get_json(silent=True)

        if not isinstance(conteudo_json, dict):
            raise ValidationError(
                {
                    "_schema": [
                        "O corpo da requisição deve ser um objeto JSON."
                    ]
                }
            )

        return dict(conteudo_json)

    dados_formulario: dict[str, Any] = request.form.to_dict(
        flat=True
    )

    anexo = request.files.get("anexo")

    if isinstance(anexo, FileStorage) and anexo.filename:
        dados_formulario["anexo"] = anexo

    return dados_formulario





@bp.post("/chat/enviar")
@bp.doc(
    security=[{"BearerAuth": []}],
    summary="Enviar mensagem para o Google Chat",
    description=(
        "Envia uma mensagem para um espaço do Google Chat "
        "por ID ou nome. Quando os dois identificadores forem "
        "informados, o ID terá prioridade."
    ),
    tags=["Gmail"],
)
@bp.response(200, EnviarMensagemGoogleChatResponseSchema)
@bp.response(400, ErroGoogleChatSchema)
@bp.response(404, ErroGoogleChatSchema)
@bp.response(409, ErroGoogleChatSchema)
@bp.response(500, ErroGoogleChatSchema)
@token_require("/gmail")
def enviar_mensagem_google_chat():
    schema = EnviarMensagemGoogleChatSchema()

    try:
        dados_requisicao = _obter_dados_google_chat()
        dados_validados = schema.load(dados_requisicao)
    except ValidationError as erro:
        return jsonify(
            {
                "success": False,
                "message": "Dados inválidos.",
                "errors": erro.messages,
            }
        ), 400

    service = GoogleChatService(
        google_chat_repository=GoogleChatRepository(),
        gmail_chat_sender=GmailChatSender(),
    )

    try:
        resultado = asyncio.run(
            service.enviar_mensagem(
                mensagem=dados_validados["mensagem"],
                id_chat=dados_validados.get("id_chat"),
                nome_chat=dados_validados.get("nome_chat"),
            )
        )
    except IdentificacaoChatInvalidaError as erro:
        return jsonify(
            {
                "success": False,
                "message": str(erro),
            }
        ), 400
    except ChatNaoEncontradoError as erro:
        return jsonify(
            {
                "success": False,
                "message": str(erro),
            }
        ), 404
    except (
        ChatInativoError,
        ChatWebhookNaoConfiguradoError,
    ) as erro:
        return jsonify(
            {
                "success": False,
                "message": str(erro),
            }
        ), 409
    except GoogleChatSendError:
        return jsonify(
            {
                "success": False,
                "message": (
                    "Não foi possível enviar a mensagem "
                    "para o Google Chat."
                ),
            }
        ), 500

    return jsonify(
        {
            "success": True,
            "message": (
                "Mensagem enviada com sucesso para o Google Chat."
            ),
            "data": resultado,
        }
    ), 200


def _obter_dados_google_chat() -> dict[str, Any]:
    if not request.is_json:
        raise ValidationError(
            {
                "_schema": [
                    "O Content-Type da requisição deve ser "
                    "application/json."
                ]
            }
        )

    conteudo_json = request.get_json(silent=True)

    if not isinstance(conteudo_json, dict):
        raise ValidationError(
            {
                "_schema": [
                    "O corpo da requisição deve ser um objeto JSON."
                ]
            }
        )

    return dict(conteudo_json)