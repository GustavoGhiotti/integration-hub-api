from typing import Any

from marshmallow import (
    Schema,
    ValidationError,
    fields,
    post_load,
    validate,
    validates,
    validates_schema,
)
from werkzeug.datastructures import FileStorage


class EnviarEmailSchema(Schema):
    assunto = fields.String(
        required=True,
        validate=validate.Length(
            min=1,
            max=255,
            error="O assunto deve possuir entre 1 e 255 caracteres.",
        ),
        error_messages={
            "required": "O assunto é obrigatório.",
            "invalid": "O assunto deve ser uma string.",
        },
        metadata={
            "description": "Assunto do e-mail.",
            "example": "Relatório mensal",
        },
    )

    destinatario = fields.Email(
        required=True,
        error_messages={
            "required": "O destinatário é obrigatório.",
            "invalid": "O destinatário deve ser um e-mail válido.",
        },
        metadata={
            "description": "Endereço de e-mail do destinatário.",
            "example": "destinatario@empresa.com.br",
        },
    )

    corpo = fields.String(
        required=True,
        validate=validate.Length(
            min=1,
            max=100_000,
            error="O corpo deve possuir entre 1 e 100.000 caracteres.",
        ),
        error_messages={
            "required": "O corpo é obrigatório.",
            "invalid": "O corpo deve ser uma string.",
        },
        metadata={
            "description": "Conteúdo textual do e-mail.",
            "example": "Segue o relatório mensal.",
        },
    )

    possuiAnexo = fields.Boolean(
        required=False,
        load_default=False,
        allow_none=True,
        truthy={"true", "True", "TRUE", "1", 1, True},
        falsy={"", "false", "False", "FALSE", "0", 0, False},
        error_messages={
            "invalid": "O campo possuiAnexo deve ser booleano.",
        },
        metadata={
            "description": (
                "Informa se o e-mail possui anexo. "
                "Quando não informado, assume false."
            ),
            "example": False,
        },
    )

    anexo = fields.Raw(
        required=False,
        allow_none=True,
        metadata={
            "type": "string",
            "format": "binary",
            "description": "Arquivo opcional anexado ao e-mail.",
        },
    )

    @validates("assunto")
    def validar_assunto(
        self,
        assunto: str,
        **kwargs: Any,
    ) -> None:
        assunto_normalizado = assunto.strip()

        if not assunto_normalizado:
            raise ValidationError(
                "O assunto não pode estar vazio."
            )

        if "\r" in assunto_normalizado or "\n" in assunto_normalizado:
            raise ValidationError(
                "O assunto contém caracteres inválidos."
            )

    @validates("destinatario")
    def validar_destinatario(
        self,
        destinatario: str,
        **kwargs: Any,
    ) -> None:
        if "\r" in destinatario or "\n" in destinatario:
            raise ValidationError(
                "O destinatário contém caracteres inválidos."
            )

    @validates("corpo")
    def validar_corpo(
        self,
        corpo: str,
        **kwargs: Any,
    ) -> None:
        if not corpo.strip():
            raise ValidationError(
                "O corpo não pode estar vazio."
            )

    @validates_schema
    def validar_anexo(
        self,
        dados: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        possui_anexo = bool(
            dados.get("possuiAnexo") or False
        )
        anexo = dados.get("anexo")

        arquivo_foi_enviado = (
            isinstance(anexo, FileStorage)
            and bool(anexo.filename)
        )

        if possui_anexo and not arquivo_foi_enviado:
            raise ValidationError(
                {
                    "anexo": [
                        "O anexo é obrigatório quando "
                        "possuiAnexo for true."
                    ]
                }
            )

        if not possui_anexo and arquivo_foi_enviado:
            raise ValidationError(
                {
                    "possuiAnexo": [
                        "Informe possuiAnexo como true "
                        "para enviar um arquivo."
                    ]
                }
            )

    @post_load
    def normalizar_dados(
        self,
        dados: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        dados["assunto"] = dados["assunto"].strip()
        dados["destinatario"] = (
            dados["destinatario"].strip().lower()
        )
        dados["corpo"] = dados["corpo"].strip()
        dados["possuiAnexo"] = bool(
            dados.get("possuiAnexo") or False
        )

        return dados


class DadosEnvioEmailResponseSchema(Schema):
    messageId = fields.String(required=True)


class EnviarEmailResponseSchema(Schema):
    success = fields.Boolean(required=True)
    message = fields.String(required=True)
    data = fields.Nested(
        DadosEnvioEmailResponseSchema,
        required=True,
    )


class ErroValidacaoEmailSchema(Schema):
    success = fields.Boolean(required=True)
    message = fields.String(required=True)
    errors = fields.Dict(
        keys=fields.String(),
        values=fields.Raw(),
        required=True,
    )