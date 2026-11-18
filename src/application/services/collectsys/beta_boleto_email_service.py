from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from html import unescape
import imaplib
import os
import re
import time


def _somente_digitos(valor) -> str:
    return "".join(char for char in str(valor or "") if char.isdigit())


def _env_str(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    return value.strip() if isinstance(value, str) else value


def _texto_mensagem(msg: EmailMessage) -> str:
    partes = []
    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        if part.get_content_type() not in ("text/plain", "text/html"):
            continue

        try:
            conteudo = part.get_content()
        except Exception:
            payload = part.get_payload(decode=True) or b""
            charset = part.get_content_charset() or "utf-8"
            conteudo = payload.decode(charset, errors="ignore")

        if part.get_content_type() == "text/html":
            conteudo = re.sub(r"<[^>]+>", " ", conteudo)
            conteudo = unescape(conteudo)
        partes.append(conteudo)

    return "\n".join(partes)


def _normalizar_decimal(valor: str) -> float | None:
    valor = str(valor or "").strip()
    if not valor:
        return None

    valor = re.sub(r"[^0-9,.]", "", valor)
    if not valor:
        return None

    if "," in valor:
        valor = valor.replace(".", "").replace(",", ".")
    try:
        return round(float(valor), 2)
    except ValueError:
        return None


def extrair_cpf_email(msg: EmailMessage) -> str | None:
    texto = _texto_mensagem(msg)
    match = re.search(r"CPF\s*:?\s*([0-9.\-]{11,14})", texto, re.IGNORECASE)
    if match:
        cpf = _somente_digitos(match.group(1))
        return cpf.zfill(11) if cpf else None

    for candidato in re.findall(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b", texto):
        cpf = _somente_digitos(candidato)
        if len(cpf) == 11:
            return cpf
    return None


def extrair_valor_entrada_email(msg: EmailMessage) -> float | None:
    texto = _texto_mensagem(msg)
    match = re.search(
        r"Valor\s+total\s+da\s+entrada\s*:?(?P<trecho>.{0,120})",
        texto,
        re.IGNORECASE | re.DOTALL,
    )
    if match:
        valor = re.search(r"(?:R\$\s*)?([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2}|[0-9]+[,.][0-9]{2})", match.group("trecho"))
        if valor:
            return _normalizar_decimal(valor.group(1))
    return None


def destinatarios_email(msg: EmailMessage) -> set[str]:
    destinatarios = set()
    for header in ("to", "delivered-to", "x-original-to", "resent-to"):
        valores = msg.get_all(header, [])
        for valor in valores:
            for email in re.findall(r"[\w.+-]+@[\w.-]+", str(valor or "").lower()):
                destinatarios.add(email)

    texto = _texto_mensagem(msg)
    for match in re.findall(r"\b(?:to|para)\s*:\s*<?([\w.+-]+@[\w.-]+)>?", texto, re.IGNORECASE):
        destinatarios.add(match.lower())

    return destinatarios


def extrair_pdf_anexo(msg: EmailMessage) -> tuple[str, bytes] | None:
    for part in msg.walk():
        filename = part.get_filename() or ""
        content_type = part.get_content_type()
        is_pdf = content_type == "application/pdf" or filename.lower().endswith(".pdf")
        if not is_pdf:
            continue

        conteudo = part.get_payload(decode=True) or b""
        if conteudo.startswith(b"%PDF"):
            return filename or "boleto_beta.pdf", conteudo
    return None


def _data_mensagem(msg: EmailMessage) -> datetime | None:
    try:
        data = parsedate_to_datetime(msg.get("date"))
        if data and data.tzinfo:
            data = data.astimezone().replace(tzinfo=None)
        return data
    except Exception:
        return None


@dataclass
class BoletoBetaEmail:
    cpf: str
    valor: float | None
    nome_anexo: str
    conteudo_pdf: bytes
    assunto: str | None = None
    data_email: str | None = None
    message_id: str | None = None
    destinatarios: tuple[str, ...] = ()


class BetaBoletoEmailService:
    def __init__(self):
        self.host = _env_str("BETA_BOLETO_IMAP_HOST", "imap.gmail.com")
        self.port = int(_env_str("BETA_BOLETO_IMAP_PORT", "993"))
        self.user = _env_str("BETA_BOLETO_IMAP_USER") or _env_str("BETA_BOLETO_EMAIL") or _env_str("SMTP_USER")
        self.password = _env_str("BETA_BOLETO_IMAP_PASSWORD") or _env_str("BETA_BOLETO_EMAIL_PASSWORD") or _env_str("SMTP_PASSWORD")
        if self.host and "gmail" in self.host.lower() and self.password:
            self.password = self.password.replace(" ", "")
        self.folder = _env_str("BETA_BOLETO_IMAP_FOLDER", "INBOX")
        self.max_messages = int(_env_str("BETA_BOLETO_IMAP_MAX_MESSAGES", "50"))
        self.trash_folder = _env_str("BETA_BOLETO_IMAP_TRASH_FOLDER")
        self.excluir_apos_download = _env_str("BETA_BOLETO_IMAP_DELETE_AFTER_DOWNLOAD", "1").lower() in (
            "1",
            "true",
            "yes",
            "sim",
        )

    def _validar_configuracao(self):
        if not self.user or not self.password:
            raise RuntimeError("Configure BETA_BOLETO_IMAP_USER/BETA_BOLETO_IMAP_PASSWORD para consultar os boletos BETA por e-mail.")
        if self.host and self.host.lower().startswith("smtp."):
            raise RuntimeError(
                f"BETA_BOLETO_IMAP_HOST esta configurado como servidor SMTP ({self.host}). "
                "Para ler os boletos recebidos, configure o servidor IMAP, por exemplo imap.gmail.com na porta 993."
            )

    def _erro_autenticacao(self) -> RuntimeError:
        dica = ""
        if self.host and "gmail" in self.host.lower():
            dica = " Para Gmail/Google Workspace, o IMAP geralmente exige senha de app, nao a senha normal da conta."
        return RuntimeError(
            f"Falha ao autenticar no email central BETA via IMAP host={self.host} user={self.user}. "
            f"Verifique BETA_BOLETO_IMAP_USER, BETA_BOLETO_IMAP_PASSWORD e se o IMAP esta habilitado.{dica}"
        )

    def validar_autenticacao(self) -> None:
        self._validar_configuracao()
        try:
            with imaplib.IMAP4_SSL(self.host, self.port) as mail:
                mail.login(self.user, self.password)
        except imaplib.IMAP4.error as exc:
            raise self._erro_autenticacao() from exc

    def _decode_mailbox(self, mailbox: bytes | str) -> str:
        if isinstance(mailbox, bytes):
            return mailbox.decode("utf-8", errors="ignore")
        return str(mailbox or "")

    def _extrair_nome_pasta(self, mailbox: bytes | str) -> str | None:
        linha = self._decode_mailbox(mailbox).strip()
        match = re.search(r' "([^"]+)"$', linha)
        if match:
            return match.group(1)

        partes = linha.rsplit(" ", 1)
        return partes[-1].strip('"') if partes else None

    def _pasta_lixeira(self, mail: imaplib.IMAP4_SSL) -> str | None:
        if self.trash_folder:
            return self.trash_folder

        status, pastas = mail.list()
        if status != "OK" or not pastas:
            return None

        candidatas = []
        for pasta in pastas:
            linha = self._decode_mailbox(pasta)
            nome = self._extrair_nome_pasta(pasta)
            if not nome:
                continue
            linha_normalizada = linha.lower()
            nome_normalizado = nome.lower()
            if "\\trash" in linha_normalizada:
                return nome
            if any(padrao in nome_normalizado for padrao in ("trash", "lixeira", "bin")):
                candidatas.append(nome)

        return candidatas[0] if candidatas else None

    def _mover_para_lixeira(self, mail: imaplib.IMAP4_SSL, msg_id: bytes) -> bool:
        pasta_lixeira = self._pasta_lixeira(mail)
        if not pasta_lixeira:
            return False

        status, _ = mail.copy(msg_id, pasta_lixeira)
        if status != "OK":
            print(f"Erro ao copiar email BETA para lixeira {pasta_lixeira}: {msg_id!r}")
            return False

        status, _ = mail.store(msg_id, "+FLAGS", "\\Deleted")
        if status == "OK":
            mail.expunge()
            return True

        print(f"Erro ao marcar email BETA como excluido apos copiar para lixeira: {msg_id!r}")
        return False

    def _excluir_email_processado(self, mail: imaplib.IMAP4_SSL, msg_id: bytes) -> None:
        if not self.excluir_apos_download:
            return

        if self._mover_para_lixeira(mail, msg_id):
            return

        status, _ = mail.store(msg_id, "+FLAGS", "\\Deleted")
        if status == "OK":
            mail.expunge()
        else:
            print(f"Erro ao marcar email BETA como excluido: {msg_id!r}")

    def _buscar_uma_vez(
        self,
        cpf_cliente: str,
        desde: datetime,
        valor_esperado: float | None = None,
        destinatario_esperado: str | None = None,
    ) -> BoletoBetaEmail | None:
        self._validar_configuracao()
        cpf_cliente = _somente_digitos(cpf_cliente).zfill(11)
        destinatario_esperado = (destinatario_esperado or "").strip().lower() or None
        valor_esperado = round(float(valor_esperado), 2) if valor_esperado is not None else None

        with imaplib.IMAP4_SSL(self.host, self.port) as mail:
            try:
                mail.login(self.user, self.password)
            except imaplib.IMAP4.error as exc:
                raise self._erro_autenticacao() from exc

            mail.select(self.folder, readonly=not self.excluir_apos_download)

            data_busca = desde.date().strftime("%d-%b-%Y")
            status, data = mail.search(None, "SINCE", data_busca)
            if status != "OK" or not data or not data[0]:
                return None

            ids = data[0].split()[-self.max_messages :]
            for msg_id in reversed(ids):
                status, payload = mail.fetch(msg_id, "(RFC822)")
                if status != "OK" or not payload:
                    continue

                raw = next((item[1] for item in payload if isinstance(item, tuple)), None)
                if not raw:
                    continue

                msg = BytesParser(policy=policy.default).parsebytes(raw)
                data_msg = _data_mensagem(msg)
                if data_msg and data_msg < desde:
                    continue

                cpf_email = extrair_cpf_email(msg)
                if cpf_email != cpf_cliente:
                    continue

                if destinatario_esperado and destinatario_esperado not in destinatarios_email(msg):
                    continue

                valor_email = extrair_valor_entrada_email(msg)
                if valor_esperado is not None:
                    if valor_email is None or abs(valor_email - valor_esperado) > 0.01:
                        continue

                anexo = extrair_pdf_anexo(msg)
                if not anexo:
                    continue

                nome_anexo, conteudo_pdf = anexo
                try:
                    self._excluir_email_processado(mail, msg_id)
                except Exception as exc:
                    print(f"Erro ao excluir email BETA processado: {exc}")
                return BoletoBetaEmail(
                    cpf=cpf_email,
                    valor=valor_email,
                    nome_anexo=nome_anexo,
                    conteudo_pdf=conteudo_pdf,
                    assunto=msg.get("subject"),
                    data_email=msg.get("date"),
                    message_id=msg.get("message-id"),
                    destinatarios=tuple(sorted(destinatarios_email(msg))),
                )

        return None

    def aguardar_boleto(
        self,
        cpf_cliente: str,
        iniciado_em: datetime | None = None,
        valor_esperado: float | None = None,
        destinatario_esperado: str | None = None,
    ) -> BoletoBetaEmail | None:
        timeout = int(os.getenv("BETA_BOLETO_EMAIL_TIMEOUT_SECONDS", "60"))
        intervalo = int(os.getenv("BETA_BOLETO_EMAIL_INTERVAL_SECONDS", "5"))
        desde = (iniciado_em or datetime.now()) - timedelta(minutes=int(os.getenv("BETA_BOLETO_EMAIL_TOLERANCE_MINUTES", "5")))
        limite = time.monotonic() + timeout

        while True:
            boleto = self._buscar_uma_vez(cpf_cliente, desde, valor_esperado, destinatario_esperado)
            if boleto:
                return boleto
            if time.monotonic() >= limite:
                return None
            time.sleep(max(intervalo, 1))
