import json
import hashlib
from src.infrastructure.repositories.sql_template_repository import TemplateRepository, NumeroRepository
from src.infrastructure.repositories.sql_controle_envios_repository import ControleEnviosRepository
from src.infrastructure.repositories.cedente_repository import CarteiraRepository
from src.infrastructure.external.twilio.twilio_client import get_twilio_client
from src.infrastructure.external.twilio.twilio_parser import parse_twilio_template
from src.domain.utils.ajusta_telefone import validar_numero_whatsapp
from datetime import datetime, timedelta


class TwilioTemplateService:
    def __init__(self):
        self.repo = TemplateRepository()

    def obter_dados_template(self, sid_template: str):
        template = self.repo.buscar_por_sid(sid_template)

        return {
            "telefoneCliente": "5599999999999",
            "idCedente": 0,
            "sidTemplate": template["sidTemplate"],
            "canal": "preventivo ou negociacao",
            "variaveis": template["variaveis"],
        }


class TwilioEnvioService:
    def __init__(self):
        self.repoTemplate = TemplateRepository()
        self.repoNumero = NumeroRepository()
        self.repoControle = ControleEnviosRepository()

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

    def _selecionar_numero_envio(self, telefone_cliente: str, numeros: list[dict]):
        if not numeros:
            raise Exception("Nenhum numero ativo encontrado para este cedente")
        if len(numeros) == 1:
            return numeros[0]

        contagens = self.repoControle.obter_contagens_do_dia(
            "TWILIO",
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

    def enviar(
        self,
        telefone_cliente: str,
        id_cedente: int,
        canal: str,
        sid_template: str,
        variaveis: dict,
        solicitante: dict | None = None,
    ):
        template = self.repoTemplate.buscar_por_sid(sid_template)
        id_cedente_solicitado = id_cedente
        id_cedente = self._normalizar_id_cedente(id_cedente)

        carteira = CarteiraRepository().buscar_por_id_cedente(id_cedente)

        chave = None
        if "cedente" in variaveis:
            chave = "cedente"
        elif "carteira" in variaveis:
            chave = "carteira"

        if chave:
            nome_variavel = str(variaveis[chave]).strip()

            if not carteira:
                raise Exception(f"Nenhuma carteira encontrada para cedente {id_cedente}")

            if id_cedente == 3:
                nome_db = nome_variavel
            else:
                nome_db = carteira["nomeCedenteFormatado"].strip()

            if not nome_variavel or nome_variavel.lower() != nome_db.lower():
                variaveis[chave] = nome_db

        canal_normalizado = canal.lower()
        if canal_normalizado == "preventivo":
            numeros_banco = self.repoNumero.buscar_numeros_preventivo(id_cedente, canal_normalizado)
        else:
            numeros_banco = self.repoNumero.buscar_numeros(id_cedente, canal_normalizado)

        numero_banco = self._selecionar_numero_envio(telefone_cliente, numeros_banco)
        telefone_cliente = validar_numero_whatsapp(telefone_cliente)
        numero_envio = validar_numero_whatsapp(numero_banco["numero"])

        formato_envio = {
            "from_": f"whatsapp:+{numero_envio}",
            "to": f"whatsapp:+{telefone_cliente}",
            "content_sid": template["sidTemplate"],
        }

        if template.get("variaveis") and variaveis:
            formato_envio["content_variables"] = json.dumps(variaveis)

        if numero_banco.get("serviceSid"):
            formato_envio["messaging_service_sid"] = numero_banco["serviceSid"]

        mensagem = get_twilio_client().messages.create(**formato_envio)
        self.repoControle.registrar_envio(
            "TWILIO",
            numero_banco["numero"],
            numero_destino=telefone_cliente,
            id_cedente=id_cedente_solicitado,
            id_cedente_normalizado=id_cedente,
            canal=canal,
            id_usuario_solicitante=(solicitante or {}).get("id"),
            usuario_solicitante=(solicitante or {}).get("usuario"),
            template=template["sidTemplate"],
            message_id=mensagem.sid,
        )

        return {
            "messageSid": mensagem.sid,
            "status": mensagem.status,
            "template": template["sidTemplate"],
            "variaveis_enviadas": variaveis,
        }


class TwilioTemplateSyncService:
    def __init__(self):
        self.client = get_twilio_client()
        self.repo = TemplateRepository()

    def obter_status_aprovacao(self, sid_template: str):
        return {"status": "Em Analise", "motivo_rejeicao": None, "data": None}

    def sincronizar_template_especifico(self, sid_template: str):
        try:
            tpl = self.client.content.v1.contents(sid_template).fetch()
            approval = self.obter_status_aprovacao(sid_template)
            parsed = parse_twilio_template(tpl, approval)
            self.repo.salvar_ou_atualizar(parsed)
            return parsed
        except Exception as e:
            print("ERRO SINCRONIZAR:", e)
            raise

    def sincronizar_por_sid(self, sid_template: str):
        return self.sincronizar_template_especifico(sid_template)

    def sincronizar_ultimos_7_dias(self):
        sete_dias_atras = datetime.utcnow() - timedelta(days=7)
        templates = self.client.content.v1.contents.list()

        contador = 0
        for tpl in templates:
            if tpl.date_created and tpl.date_created.replace(tzinfo=None) < sete_dias_atras:
                continue

            approval = self.obter_status_aprovacao(tpl.sid)
            parsed = parse_twilio_template(tpl, approval)
            self.repo.salvar_ou_atualizar(parsed)
            contador += 1

        return {"status": "ok", "total": contador}
