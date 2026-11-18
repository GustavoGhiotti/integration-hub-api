import mimetypes
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path
from typing import Final

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from src.domain.exceptions.envio_email_exception import (
    EmailAttachmentError,
    EmailConfigurationError,
    EmailDeliveryError,
)


MAX_ATTACHMENT_BYTES: Final[int] = 10 * 1024 * 1024

BLOCKED_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {
        ".bat",
        ".cmd",
        ".com",
        ".exe",
        ".js",
        ".msi",
        ".ps1",
        ".sh",
        ".vbs",
    }
)


class GmailSmtpSender:
    def __init__(
        self,
        *,
        sender_email: str,
        sender_password: str,
        max_attachment_bytes: int = MAX_ATTACHMENT_BYTES,
    ) -> None:
        email_normalizado = sender_email.strip()
        senha_normalizada = sender_password.strip()

        if not email_normalizado or not senha_normalizada:
            raise EmailConfigurationError(
                "As variáveis EMAIL e EMAIL_SENHA "
                "devem estar configuradas."
            )

        if max_attachment_bytes <= 0:
            raise EmailConfigurationError(
                "EMAIL_MAX_ATTACHMENT_BYTES deve ser maior que zero."
            )

        self._sender_email = email_normalizado
        self._sender_password = senha_normalizada
        self._max_attachment_bytes = max_attachment_bytes

    @classmethod
    def from_environment(cls) -> "GmailSmtpSender":
        limite_configurado = os.getenv(
            "EMAIL_MAX_ATTACHMENT_BYTES",
            str(MAX_ATTACHMENT_BYTES),
        )

        try:
            limite_anexo = int(limite_configurado)
        except ValueError as erro:
            raise EmailConfigurationError(
                "EMAIL_MAX_ATTACHMENT_BYTES deve ser um número inteiro."
            ) from erro

        return cls(
            sender_email=os.getenv("EMAIL", ""),
            sender_password=os.getenv("EMAIL_SENHA", ""),
            max_attachment_bytes=limite_anexo,
        )

    def send(
        self,
        *,
        subject: str,
        recipient: str,
        body: str,
        attachment: FileStorage | None = None,
    ) -> str:
        message = self._criar_mensagem(
            subject=subject,
            recipient=recipient,
            body=body,
            attachment=attachment,
        )

        try:
            ssl_context = ssl.create_default_context()

            with smtplib.SMTP_SSL(
                host="smtp.gmail.com",
                port=465,
                context=ssl_context,
                timeout=20,
            ) as smtp:
                smtp.login(
                    self._sender_email,
                    self._sender_password,
                )
                smtp.send_message(
                    message,
                    from_addr=self._sender_email,
                    to_addrs=[recipient],
                )

        except smtplib.SMTPAuthenticationError as erro:
            raise EmailDeliveryError(
                "Não foi possível autenticar no serviço de e-mail."
            ) from erro

        except (smtplib.SMTPException, OSError) as erro:
            raise EmailDeliveryError(
                "Não foi possível enviar o e-mail."
            ) from erro

        return str(message["Message-ID"])

    def _criar_mensagem(
        self,
        *,
        subject: str,
        recipient: str,
        body: str,
        attachment: FileStorage | None,
    ) -> EmailMessage:
        message = EmailMessage()
        message["Message-ID"] = make_msgid()
        message["From"] = self._sender_email
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)

        if attachment is not None:
            self._add_attachment(
                message=message,
                attachment=attachment,
            )

        return message

    def _add_attachment(
        self,
        *,
        message: EmailMessage,
        attachment: FileStorage,
    ) -> None:
        original_name = secure_filename(
            attachment.filename or ""
        )

        if not original_name:
            raise EmailAttachmentError(
                "Nome do arquivo inválido."
            )

        extension = Path(original_name).suffix.lower()

        if extension in BLOCKED_EXTENSIONS:
            raise EmailAttachmentError(
                "Tipo de arquivo não permitido."
            )

        content = attachment.stream.read(
            self._max_attachment_bytes + 1
        )
        attachment.stream.seek(0)

        if len(content) > self._max_attachment_bytes:
            raise EmailAttachmentError(
                "O anexo excede o tamanho permitido."
            )

        mime_type, _ = mimetypes.guess_type(original_name)
        content_type = mime_type or "application/octet-stream"
        main_type, sub_type = content_type.split("/", maxsplit=1)

        message.add_attachment(
            content,
            maintype=main_type,
            subtype=sub_type,
            filename=original_name,
        )