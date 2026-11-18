import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from email.utils import parseaddr
from typing import Any, Protocol

from src.domain.exceptions.envio_email_exception import (
    EmailDeliveryError,
    EmailValidationError,
)
from src.infrastructure.external.gmail.gmail_smtp_sender import (
    GmailSmtpSender,
)


PADRAO_EMAIL = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)


@dataclass(frozen=True, slots=True)
class ResultadoEnvioEmail:
    destinatarios: tuple[str, ...]
    identificadores_mensagem: tuple[str, ...]

    @property
    def quantidade_enviada(self) -> int:
        return len(self.identificadores_mensagem)


class EnviadorEmail(Protocol):
    def send(
        self,
        *,
        subject: str,
        recipient: str,
        body: str,
        attachment: Any | None = None,
    ) -> str:
        ...

class ChamadoEnvioEmailService:
    """
    Serviço de aplicação para envio de e-mails de chamados.

    Envia uma mensagem individual por destinatário. Isso evita expor os
    endereços dos demais destinatários no cabeçalho To do e-mail.
    """

    def __init__(
        self,
        enviador_email: EnviadorEmail | None = None,
    ) -> None:
        self._enviador_email = (
            enviador_email
            if enviador_email is not None
            else GmailSmtpSender.from_environment()
        )

    def enviar(
        self,
        dados: Mapping[str, Any],
    ) -> ResultadoEnvioEmail:
        assunto = self._obter_texto_obrigatorio(
            dados=dados,
            campo="assunto",
        )
        corpo = self._obter_texto_obrigatorio(
            dados=dados,
            campo="corpo",
        )
        destinatarios = self._obter_destinatarios(dados)
        anexo = dados.get("anexo")

        identificadores_mensagem: list[str] = []

        for destinatario in destinatarios:
            try:
                identificador = self._enviador_email.send(
                    subject=assunto,
                    recipient=destinatario,
                    body=corpo,
                    attachment=anexo,
                )
            except EmailDeliveryError:
                raise
            except Exception as erro:
                raise EmailDeliveryError(
                    "Não foi possível enviar o e-mail."
                ) from erro

            identificadores_mensagem.append(identificador)

        return ResultadoEnvioEmail(
            destinatarios=destinatarios,
            identificadores_mensagem=tuple(
                identificadores_mensagem
            ),
        )

    @staticmethod
    def _obter_texto_obrigatorio(
        *,
        dados: Mapping[str, Any],
        campo: str,
    ) -> str:
        valor = dados.get(campo)

        if not isinstance(valor, str):
            raise EmailValidationError(
                campo,
                f"O campo {campo} deve ser uma string.",
            )

        valor_normalizado = valor.strip()

        if not valor_normalizado:
            raise EmailValidationError(
                campo,
                f"O campo {campo} é obrigatório.",
            )

        if "\r" in valor_normalizado or "\n" in valor_normalizado:
            raise EmailValidationError(
                campo,
                f"O campo {campo} contém caracteres inválidos.",
            )

        return valor_normalizado

    @classmethod
    def _obter_destinatarios(
        cls,
        dados: Mapping[str, Any],
    ) -> tuple[str, ...]:
        valor = dados.get("destinatarios")

        if valor is None:
            valor = dados.get("destinatario")

        if isinstance(valor, str):
            destinatarios_brutos = (valor,)

        elif (
            isinstance(valor, Sequence)
            and not isinstance(valor, bytes)
        ):
            destinatarios_brutos = tuple(valor)

        else:
            raise EmailValidationError(
                "destinatario",
                "Informe ao menos um destinatário válido.",
            )

        destinatarios_normalizados: list[str] = []

        for destinatario in destinatarios_brutos:
            destinatario_normalizado = cls._normalizar_email(
                destinatario
            )

            if destinatario_normalizado not in destinatarios_normalizados:
                destinatarios_normalizados.append(
                    destinatario_normalizado
                )

        if not destinatarios_normalizados:
            raise EmailValidationError(
                "destinatario",
                "Informe ao menos um destinatário válido.",
            )

        return tuple(destinatarios_normalizados)

    @staticmethod
    def _normalizar_email(
        destinatario: Any,
    ) -> str:
        if not isinstance(destinatario, str):
            raise EmailValidationError(
                "destinatario",
                "O destinatário deve ser um e-mail válido.",
            )

        email_normalizado = destinatario.strip().lower()

        if (
            not email_normalizado
            or "\r" in email_normalizado
            or "\n" in email_normalizado
        ):
            raise EmailValidationError(
                "destinatario",
                "O destinatário deve ser um e-mail válido.",
            )

        nome, email_extraido = parseaddr(email_normalizado)

        if (
            nome
            or email_extraido != email_normalizado
            or not PADRAO_EMAIL.fullmatch(email_normalizado)
        ):
            raise EmailValidationError(
                "destinatario",
                "O destinatário deve ser um e-mail válido.",
            )

        return email_normalizado