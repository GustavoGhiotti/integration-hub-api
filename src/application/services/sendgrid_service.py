import json
import hashlib
import logging
from datetime import datetime, timezone

log = logging.getLogger("sendgrid_webhook")

# Evento do SendGrid -> categoria de negócio (facilita o relatório do MIS).
_CATEGORIA = {
    "processed":        "ENVIO",
    "deferred":         "ADIADO",
    "delivered":        "ENTREGA",
    "open":             "ABERTURA",
    "click":            "CLIQUE",
    "bounce":           "FALHA",
    "dropped":          "FALHA",
    "spamreport":       "RECLAMACAO",
    "unsubscribe":      "DESCADASTRO",
    "group_unsubscribe": "DESCADASTRO",
    "group_resubscribe": "DESCADASTRO",
}


def _categoria(evento: str) -> str:
    return _CATEGORIA.get(evento, "OUTRO")


def _norm_message_id(valor):
    """O sg_message_id vem como '<id_base>.filtroX.Y'. A parte antes do primeiro
    '.' é estável entre os eventos do mesmo envio -> usamos ela para correlacionar
    processed/delivered/open/click do mesmo e-mail."""
    if not valor:
        return None
    base = str(valor).split(".", 1)[0].strip()
    return base[:255] or None


def _to_dt(ts):
    """Timestamp Unix (segundos) -> datetime UTC naive (compatível com datetime2)."""
    if ts in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).replace(tzinfo=None)
    except (ValueError, OSError, OverflowError, TypeError):
        return None


def _txt(valor, limite):
    if valor is None:
        return None
    s = str(valor).strip()
    if not s:
        return None
    return s[:limite]


class SendGridService:
    """Transforma o payload do webhook do SendGrid em linhas prontas para
    gravação em lote. NÃO acessa banco — isso é responsabilidade do
    repositório/consumidor."""

    # Mesma ordem esperada por SqlEmailEventRepository.COLUNAS_EVENTO
    COLUNAS = (
        "SG_EVENT_ID", "EVENTO", "CATEGORIA", "EMAIL", "MESSAGE_ID", "TEMPLATE_ID",
        "DATA_EVENTO", "MOTIVO", "STATUS_SMTP", "TIPO_BOUNCE", "URL", "USER_AGENT", "IP", "RAW_ID",
        "ID_CEDENTE",
    )

    def parse_body(self, body: str, raw_id=None) -> list:
        """Recebe o corpo bruto (JSON) de UMA linha da RAW e devolve a lista de
        tuplas de eventos. Levanta exceção se o JSON for inválido (o consumidor
        trata marcando a linha como erro de parse)."""
        payload = json.loads(body)
        if isinstance(payload, dict):
            payload = [payload]
        if not isinstance(payload, list):
            return []

        linhas = []
        for ev in payload:
            linha = self.parse_evento(ev, raw_id)
            if linha is not None:
                linhas.append(linha)
        return linhas

    def parse_evento(self, ev: dict, raw_id=None):
        if not isinstance(ev, dict):
            return None

        evento = _txt(ev.get("event") or ev.get("event_type"), 50)
        evento = evento.lower() if evento else "outro"

        email = (_txt(ev.get("email") or ev.get("to_email") or ev.get("to"), 320) or "").lower()
        message_id = _norm_message_id(
            ev.get("sg_message_id") or ev.get("smtp-id") or ev.get("msg_id")
        )

        sg_event_id = _txt(ev.get("sg_event_id"), 100)
        if not sg_event_id:
            # Sem sg_event_id: gera uma chave determinística para não duplicar em retries.
            base = f"{message_id}|{evento}|{ev.get('timestamp')}|{email}"
            sg_event_id = hashlib.sha1(base.encode("utf-8", "ignore")).hexdigest()

        # id_cedente vem via custom_args do robô de disparo (ainda não implementado
        # no robô). Aceita tanto o dict custom_args/unique_args quanto o campo no
        # topo do evento, para funcionar automaticamente quando o robô começar a enviar.
        meta = ev.get("custom_args") or ev.get("unique_args") or {}
        if not isinstance(meta, dict):
            meta = {}
        id_cedente = _txt(
            meta.get("id_cedente") or meta.get("idCedente") or ev.get("id_cedente"),
            100,
        )

        # template_id nativo do SendGrid nao vem de forma confiavel em todos os
        # eventos; o robo passa a mandar via custom_args (id_template). Prefere o
        # nativo quando existir e cai no custom_args (aninhado ou no topo).
        template_id = _txt(
            ev.get("template_id") or meta.get("id_template") or ev.get("id_template"),
            100,
        )

        return (
            sg_event_id,
            evento,
            _categoria(evento),
            email,
            message_id,
            template_id,
            _to_dt(ev.get("timestamp")),
            _txt(ev.get("reason"), 1000),
            _txt(ev.get("status"), 50),
            _txt(ev.get("type"), 20),
            _txt(ev.get("url"), 2048),
            _txt(ev.get("useragent"), 500),
            _txt(ev.get("ip"), 45),
            raw_id,
            id_cedente,
        )
