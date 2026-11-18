import os
import hashlib
from urllib.parse import urlparse
from src.infrastructure.repositories.sql_infobip_repository import (
    InfobipTemplateRepository,
    InfobipNumeroRepository,
)
from src.infrastructure.repositories.sql_controle_envios_repository import ControleEnviosRepository
from src.infrastructure.repositories.cedente_repository import CarteiraRepository
from src.infrastructure.external.infobip.infobip_client import InfobipClient
from src.domain.utils.ajusta_telefone import validar_numero_whatsapp
from src.domain.exceptions import InfobipNumeroIndisponivelException


def _filename_from_url(media_url: str) -> str:
    parsed = urlparse(media_url)
    path = parsed.path or ""
    file_name = path.rsplit("/", 1)[-1] if "/" in path else path
    if not file_name:
        return "documento.pdf"
    if ".pdf" in file_name.lower():
        idx = file_name.lower().find(".pdf")
        return file_name[: idx + 4]
    return file_name


class InfobipTemplateService:
    def __init__(self):
        self.repo = InfobipTemplateRepository()

    def _montar_variaveis_envio(self, template: dict):
        variaveis_template = template.get("variaveis") or {}
        variaveis_envio = {}

        body_vars = []
        if isinstance(variaveis_template, dict):
            body_vars = variaveis_template.get("body") or []
        elif isinstance(variaveis_template, list):
            body_vars = variaveis_template

        for key in body_vars:
            variaveis_envio[str(key)] = ""

        if template.get("media"):
            variaveis_envio["url"] = ""

        if template.get("acoes"):
            variaveis_envio["buttons"] = []

        return variaveis_envio

    def obter_dados_template(self, nome_template: str):
        template = self.repo.buscar_por_nome(nome_template)

        return {
            "telefoneCliente": "5599999999999",
            "idCedente": 0,
            "sidTemplate": template["nomeTemplate"],
            "canal": "preventivo ou negociacao",
            "variaveis": self._montar_variaveis_envio(template),
        }


class InfobipEnvioService:
    def __init__(self):
        self.repoTemplate = InfobipTemplateRepository()
        self.repoNumero = InfobipNumeroRepository()
        self.repoControle = ControleEnviosRepository()
        self.client = InfobipClient()
        self.use_db = os.getenv("INFOBIP_USE_DB", "0").strip().lower() in ("1", "true", "yes")

    def _selecionar_numero_envio(self, telefone_cliente: str, numeros: list[dict]):
        if not numeros:
            raise InfobipNumeroIndisponivelException("Nao tem numero para envio disponivel")
        if len(numeros) == 1:
            return numeros[0]

        contagens = self.repoControle.obter_contagens_do_dia(
            "INFOBIP",
            [numero["numero"] for numero in numeros],
        )
        menor_qtd = min(contagens.get(numero["numero"], 0) for numero in numeros)
        candidatos = [
            numero for numero in numeros
            if contagens.get(numero["numero"], 0) == menor_qtd
        ]
        if len(candidatos) == 1:
            return candidatos[0]

        chave = validar_numero_whatsapp(telefone_cliente)
        indice = int(hashlib.sha256(chave.encode("utf-8")).hexdigest(), 16) % len(candidatos)
        return candidatos[indice]

    def _obter_template(self, template_id: str, variaveis: dict):
        try:
            return self.repoTemplate.buscar_por_sid(template_id)
        except Exception:
            try:
                return self.repoTemplate.buscar_por_nome(template_id)
            except Exception:
                if self.use_db:
                    raise
            return {
                "sidTemplate": template_id,
                "nomeTemplate": template_id,
                "lingua": "pt_BR",
                "variaveis": {"body": list((variaveis or {}).keys())},
                "tipos": ["body"],
                "corpos": {},
                "acoes": {},
                "media": {},
                "titulos": {},
                "subtitulos": {},
            }

    def _normalizar_id_cedente(self, id_cedente: int):
        match id_cedente:
            case 72 | 73 | 76 | 87:
                return 65
            case 78 | 79 | 80 | 84 | 86:
                return 77
            case 67:
                return 53
            case 50 | 54:
                return 61
            case _:
                return id_cedente

    def _ajustar_variavel_cedente(self, id_cedente: int, variaveis: dict):
        carteira = self._buscar_carteira(id_cedente)

        chave = None
        if "cedente" in variaveis:
            chave = "cedente"
        elif "carteira" in variaveis:
            chave = "carteira"

        if not chave or not carteira:
            return variaveis

        nome_variavel = str(variaveis[chave]).strip()
        if id_cedente == 3:
            nome_db = nome_variavel
        else:
            nome_db = carteira["nomeCedenteFormatado"].strip()

        if not nome_variavel or nome_variavel.lower() != nome_db.lower():
            variaveis[chave] = nome_db

        return variaveis

    def _buscar_carteira(self, id_cedente: int):
        try:
            return CarteiraRepository().buscar_por_id_cedente(id_cedente)
        except Exception:
            return None

    def _buscar_numero_origem(self, id_cedente: int, canal: str):
        canal_normalizado = canal.lower()
        carteira = self._buscar_carteira(id_cedente)
        nome_carteira = (carteira or {}).get("nomeCedenteFormatado")
        if canal_normalizado == "preventivo":
            return self.repoNumero.buscar_numeros_preventivo(
                id_cedente,
                canal_normalizado,
                nome_carteira=nome_carteira,
            )
        return self.repoNumero.buscar_numeros(id_cedente, canal_normalizado, nome_carteira)

    def _montar_placeholders(self, template: dict, variaveis: dict):
        reserved_keys = {"buttons", "header"}
        header = variaveis.get("header") if isinstance(variaveis, dict) else None
        auto_media_url = variaveis.get("url") if isinstance(variaveis, dict) else None
        if header and auto_media_url:
            reserved_keys.add("url")

        variaveis_payload = {
            k: v for k, v in (variaveis or {}).items()
            if k not in reserved_keys
        }

        variaveis_template = template.get("variaveis") or {}
        body_vars = []
        if isinstance(variaveis_template, dict):
            body_vars = variaveis_template.get("body") or []
        elif isinstance(variaveis_template, list):
            body_vars = variaveis_template

        if body_vars:
            return [str(variaveis_payload.get(str(key), "")) for key in body_vars]

        chaves_numericas = [k for k in variaveis_payload.keys() if str(k).isdigit()]
        if chaves_numericas:
            chaves_ordenadas = sorted(chaves_numericas, key=lambda x: int(str(x)))
            return [str(variaveis_payload[k]) for k in chaves_ordenadas]

        return [str(v) for v in variaveis_payload.values()]

    def _normalizar_linguagem(self, linguagem: str | None):
        if not linguagem:
            return "pt_BR"

        linguagem_normalizada = str(linguagem).strip()
        mapa = {
            "Portuguese (BR)": "pt_BR",
            "Portuguese (POR)": "pt_PT",
            "Portuguese (PT)": "pt_PT",
            "pt-BR": "pt_BR",
            "pt_BR": "pt_BR",
            "pt-PT": "pt_PT",
            "pt_PT": "pt_PT",
            "en": "en",
            "en_US": "en_US",
            "English": "en",
        }

        return mapa.get(linguagem_normalizada, linguagem_normalizada.replace("-", "_"))

    def _extrair_variaveis_envio(self, variaveis: dict):
        if not isinstance(variaveis, dict):
            return {}

        body = variaveis.get("body")
        if isinstance(body, dict):
            variaveis_normalizadas = dict(body)

            if "header" in variaveis and "header" not in variaveis_normalizadas:
                variaveis_normalizadas["header"] = variaveis["header"]
            if "buttons" in variaveis and "buttons" not in variaveis_normalizadas:
                variaveis_normalizadas["buttons"] = variaveis["buttons"]
            if "url" in variaveis and "url" not in variaveis_normalizadas:
                variaveis_normalizadas["url"] = variaveis["url"]

            return variaveis_normalizadas

        return variaveis

    def _montar_payload_base(self, template: dict, sender: str, telefone_cliente: str, placeholders: list[str]):
        return {
            "messages": [
                {
                    "from": sender,
                    "to": telefone_cliente,
                    "content": {
                        "templateName": template["nomeTemplate"],
                        "language": self._normalizar_linguagem(template.get("lingua")),
                        "templateData": {"body": {"placeholders": placeholders}},
                    },
                }
            ]
        }

    def enviar(
        self,
        telefone_cliente: str,
        id_cedente: int,
        canal: str,
        sid_template: str,
        variaveis: dict,
        solicitante: dict | None = None,
    ):
        variaveis = self._extrair_variaveis_envio(variaveis or {})
        template = self._obter_template(sid_template, variaveis)
        id_cedente_solicitado = id_cedente
        id_cedente = self._normalizar_id_cedente(id_cedente)
        variaveis = self._ajustar_variavel_cedente(id_cedente, variaveis)

        numeros_banco = self._buscar_numero_origem(id_cedente, canal)
        numero_banco = self._selecionar_numero_envio(telefone_cliente, numeros_banco)
        numero_origem = numero_banco["numero"]
        sender = numero_origem

        telefone_cliente = validar_numero_whatsapp(telefone_cliente)
        numero_envio = validar_numero_whatsapp(numero_origem)
        sender = sender or numero_envio

        header = variaveis.get("header") if isinstance(variaveis, dict) else None
        auto_media_url = variaveis.get("url") if isinstance(variaveis, dict) else None
        if not isinstance(header, dict) and auto_media_url:
            header = {
                "type": "DOCUMENT",
                "mediaUrl": auto_media_url,
                "filename": _filename_from_url(auto_media_url),
            }

        placeholders = self._montar_placeholders(template, variaveis)
        payload = self._montar_payload_base(template, sender, telefone_cliente, placeholders)

        buttons = variaveis.get("buttons") if isinstance(variaveis, dict) else None
        if isinstance(buttons, list) and buttons:
            content = payload["messages"][0].setdefault("content", {})
            template_data = content.setdefault("templateData", {})
            template_data["buttons"] = buttons

        if isinstance(header, dict) and header:
            content = payload["messages"][0].setdefault("content", {})
            template_data = content.setdefault("templateData", {})
            header_payload = {
                "type": header.get("type") or "DOCUMENT",
                "mediaUrl": header.get("mediaUrl"),
                "filename": header.get("filename"),
            }
            if header_payload["mediaUrl"] and header_payload["filename"]:
                template_data["header"] = header_payload

        resposta = self.client.send_whatsapp_template(payload)

        message_id = None
        status = None

        if isinstance(resposta, dict):
            message_id = resposta.get("messageId")
            status = resposta.get("status")
            if not message_id and resposta.get("messages"):
                message_id = resposta["messages"][0].get("messageId")
            if not status and resposta.get("messages"):
                status = resposta["messages"][0].get("status", {}).get("name")

        self.repoControle.registrar_envio(
            "INFOBIP",
            numero_banco["numero"],
            numero_destino=telefone_cliente,
            id_cedente=id_cedente_solicitado,
            id_cedente_normalizado=id_cedente,
            canal=canal,
            id_usuario_solicitante=(solicitante or {}).get("id"),
            usuario_solicitante=(solicitante or {}).get("usuario"),
            template=template["sidTemplate"],
            message_id=message_id,
        )

        return {
            "messageSid": message_id,
            "status": status or "submitted",
            "template": template["sidTemplate"],
            "variaveis_enviadas": variaveis,
        }
