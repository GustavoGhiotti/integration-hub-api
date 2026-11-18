from typing import Any

from marshmallow import (
    Schema,
    ValidationError,
    fields,
    pre_load,
    validate,
    validates_schema,
)


def validar_id_chat(
    valor: int,
) -> None:
    if isinstance(valor, bool) or valor <= 0:
        raise ValidationError(
            "O ID do chat deve ser um número inteiro positivo."
        )


class EnviarMensagemGoogleChatSchema(Schema):
    id_chat = fields.Integer(
        required=False,
        allow_none=True,
        validate=validar_id_chat,
    )

    nome_chat = fields.String(
        required=False,
        allow_none=True,
        validate=validate.Length(max=150),
    )

    mensagem = fields.String(
        required=True,
        allow_none=False,
        validate=validate.Length(max=4000),
    )

    @pre_load
    def normalizar_campos(
        self,
        dados: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        if not isinstance(dados, dict):
            return dados

        dados_normalizados = dict(dados)

        id_chat = dados_normalizados.get("id_chat")

        if id_chat is not None and (
            not isinstance(id_chat, int)
            or isinstance(id_chat, bool)
        ):
            raise ValidationError(
                {
                    "id_chat": [
                        "O ID do chat deve ser um número inteiro positivo."
                    ]
                }
            )

        nome_chat = dados_normalizados.get("nome_chat")
        mensagem = dados_normalizados.get("mensagem")

        if isinstance(nome_chat, str):
            dados_normalizados["nome_chat"] = nome_chat.strip()

        if isinstance(mensagem, str):
            dados_normalizados["mensagem"] = mensagem.strip()

        return dados_normalizados

    @validates_schema
    def validar_dados(
        self,
        dados: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        id_chat = dados.get("id_chat")
        nome_chat = dados.get("nome_chat")
        mensagem = dados.get("mensagem")

        if id_chat is None and not nome_chat:
            raise ValidationError(
                "Informe o ID ou o nome do chat.",
                field_name="_schema",
            )

        if not mensagem:
            raise ValidationError(
                "A mensagem é obrigatória.",
                field_name="mensagem",
            )


class GoogleChatEnviadoDataSchema(Schema):
    id_chat = fields.Integer(required=True)
    nome_chat = fields.String(required=True)


class EnviarMensagemGoogleChatResponseSchema(Schema):
    success = fields.Boolean(required=True)
    message = fields.String(required=True)
    data = fields.Nested(
        GoogleChatEnviadoDataSchema,
        required=True,
    )


class ErroGoogleChatSchema(Schema):
    success = fields.Boolean(required=True)
    message = fields.String(required=True)
    errors = fields.Dict(required=False)