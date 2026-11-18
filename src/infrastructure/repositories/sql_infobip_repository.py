import json
import re
from unidecode import unidecode
from src.infrastructure.database.sql_server_connection import SQLServerConnection
from src.shared.utils.env_load import DB_66
from src.domain.exceptions import InfobipNumeroIndisponivelException


class InfobipTemplateRepository:
    def __init__(self):
        self.db = SQLServerConnection(server=DB_66, database="DB_CHATBOT")

    def _map_row(self, row):
        def parse_json(v):
            if not v:
                return None
            try:
                return json.loads(v)
            except Exception:
                return None

        return {
            "sidTemplate": row["SID_TEMPLATE"],
            "nomeTemplate": row["NOME_TEMPLATE"],
            "lingua": row["LINGUA"],
            "variaveis": parse_json(row.get("VARIAVEIS")),
            "tipos": parse_json(row.get("TIPOS")),
            "corpos": parse_json(row.get("CORPOS")),
            "acoes": parse_json(row.get("ACOES")),
            "media": parse_json(row.get("MEDIA")),
            "titulos": parse_json(row.get("TITULOS")),
            "subtitulos": parse_json(row.get("SUBTITULOS")),
            "statusAprovacao": row.get("STATUS_APROVACAO"),
            "motivoRejeicao": row.get("MOTIVO_REJEICAO"),
            "dataAprovacao": row.get("DATA_APROVACAO"),
        }

    def buscar_por_sid(self, sid_template: str):
        query = """
            SELECT 
                SID_TEMPLATE,
                NOME_TEMPLATE,
                LINGUA,
                VARIAVEIS,
                TIPOS,
                CORPOS,
                ACOES,
                MEDIA,
                TITULOS,
                SUBTITULOS,
                STATUS_APROVACAO,
                MOTIVO_REJEICAO,
                DATA_APROVACAO
            FROM INFOBIP.TB_TEMPLATES WITH (NOLOCK)
            WHERE SID_TEMPLATE = ?
        """

        rows = self.db.execute(query=query, parametros=(sid_template,), fetch=True)
        if not rows:
            raise Exception(f"Template nao encontrado pelo SID '{sid_template}'.")

        return self._map_row(rows[0])

    def buscar_por_nome(self, nome_template: str):
        query = """
            SELECT 
                SID_TEMPLATE,
                NOME_TEMPLATE,
                LINGUA,
                VARIAVEIS,
                TIPOS,
                CORPOS,
                ACOES,
                MEDIA,
                TITULOS,
                SUBTITULOS,
                STATUS_APROVACAO,
                MOTIVO_REJEICAO,
                DATA_APROVACAO
            FROM INFOBIP.TB_TEMPLATES WITH (NOLOCK)
            WHERE NOME_TEMPLATE = ?
        """

        rows = self.db.execute(query=query, parametros=(nome_template,), fetch=True)
        if not rows:
            raise Exception(f"Template nao encontrado pelo nome '{nome_template}'.")

        return self._map_row(rows[0])


class InfobipNumeroRepository:
    def __init__(self):
        self.db = SQLServerConnection(server=DB_66, database="DB_CHATBOT")

    def _normalizar_texto(self, texto: str | None):
        texto = unidecode(str(texto or "")).upper()
        texto = re.sub(r"\bWGA\b", " ", texto)
        texto = re.sub(r"[^A-Z0-9]+", " ", texto)
        return " ".join(texto.split())

    def _extrair_carteiras_permitidas(self, valor: str | None):
        carteiras = []
        for item in str(valor or "").split(";"):
            item = item.strip()
            if not item or ":" not in item:
                continue

            id_cedente_raw, nome = item.split(":", 1)
            try:
                id_cedente = int(id_cedente_raw.strip())
            except (TypeError, ValueError):
                continue

            carteiras.append((id_cedente, self._normalizar_texto(nome)))

        return carteiras

    def _nome_carteira_compativel(self, cedente_numero: str | None, nome_carteira: str | None):
        cedente_normalizado = self._normalizar_texto(cedente_numero)
        carteira_normalizada = self._normalizar_texto(nome_carteira)

        if not cedente_normalizado or not carteira_normalizada:
            return False

        return (
            cedente_normalizado in carteira_normalizada
            or carteira_normalizada in cedente_normalizado
        )

    def _eh_numero_geral(self, numero: dict):
        cedente = self._normalizar_texto(numero.get("cedente"))
        return cedente in ("GRUPO ACME", "ACME")

    def _numero_permitido(self, numero: dict, id_cedente: int, nome_carteira: str | None):
        carteiras_permitidas = self._extrair_carteiras_permitidas(numero.get("carteirasPermitidas"))

        if carteiras_permitidas:
            return any(
                id_permitido == 0 and nome_permitido == "GERAL"
                or id_permitido == int(id_cedente or 0)
                for id_permitido, nome_permitido in carteiras_permitidas
            )

        if self._nome_carteira_compativel(numero.get("cedente"), nome_carteira):
            return True

        return self._eh_numero_geral(numero)

    def _map_numero_row(self, row):
        if isinstance(row, str):
            return {
                "numero": row,
                "sender": None,
                "status": None,
                "cedente": None,
                "statusRegistro": None,
                "statusRemetente": None,
                "limiteMensagens24h": None,
                "provedor": None,
                "ativo": None,
                "carteirasPermitidas": None,
            }
        if isinstance(row, (list, tuple)):
            return {
                "numero": row[0] if len(row) > 0 else None,
                "sender": row[1] if len(row) > 1 else None,
                "status": row[2] if len(row) > 2 else None,
                "cedente": row[3] if len(row) > 3 else None,
                "statusRegistro": row[4] if len(row) > 4 else None,
                "statusRemetente": row[5] if len(row) > 5 else None,
                "limiteMensagens24h": row[6] if len(row) > 6 else None,
                "provedor": row[7] if len(row) > 7 else None,
                "ativo": row[8] if len(row) > 8 else None,
                "carteirasPermitidas": row[9] if len(row) > 9 else None,
            }
        return {
            "numero": row["NUMERO"],
            "sender": row.get("SENDER"),
            "status": row.get("STATUS"),
            "cedente": row.get("CEDENTE"),
            "statusRegistro": row.get("STATUS_REGISTRO"),
            "statusRemetente": row.get("STATUS_REMETENTE"),
            "limiteMensagens24h": row.get("LIMITE_MENSAGENS_24H"),
            "provedor": row.get("PROVEDOR"),
            "ativo": row.get("ATIVO"),
            "carteirasPermitidas": row.get("CARTEIRAS_PERMITIDAS"),
        }

    def _buscar_numeros(self, canal: str, id_cedente: int, nome_carteira: str | None = None):
        query = """
            SELECT
                NUMERO,
                NOME_EXIBICAO AS SENDER,
                STATUS,
                CEDENTE,
                STATUS_REGISTRO,
                STATUS_REMETENTE,
                LIMITE_MENSAGENS_24H,
                PROVEDOR,
                ATIVO,
                CARTEIRAS_PERMITIDAS
            FROM INFOBIP.TB_NUMEROS WITH (NOLOCK)
            WHERE 1=1
              AND ISNULL(ID_CEDENTE, 0) <> -1
              AND ISNULL(ATIVO, 0) = 1
              AND ISNULL(NUMERO_VALIDO, 0) = 1
              AND UPPER(ISNULL(CANAL, '')) = 'WHATSAPP'
              AND UPPER(PROVEDOR) = 'INFOBIP'
              AND UPPER(ISNULL(STATUS, '')) = 'HIGH'
              AND UPPER(ISNULL(STATUS_REGISTRO, '')) = 'ATIVADO'
              AND UPPER(ISNULL(STATUS_REMETENTE, '')) = 'CONECTADO'
              AND ISNULL(LIMITE_MENSAGENS_24H, 0) > 0
              AND CEDENTE <> '-'
            ORDER BY
                ID ASC
        """
        rows = self.db.execute(query=query, parametros=(), fetch=True)
        if not rows:
            raise InfobipNumeroIndisponivelException("Nao tem numero para envio disponivel")

        numeros = [self._map_numero_row(row) for row in rows]
        numeros_permitidos = [
            numero for numero in numeros
            if self._numero_permitido(numero, id_cedente, nome_carteira)
        ]
        if not numeros_permitidos:
            raise InfobipNumeroIndisponivelException("Nao tem numero para envio disponivel")

        return numeros_permitidos

    def buscar_numero_preventivo(self, id_cedente: int, canal: str, id_cedente_fallback: int = 100):
        return self._buscar_numeros(canal, id_cedente)[0]

    def buscar_numero(self, id_cedente: int, canal: str, nome_carteira: str | None = None):
        return self._buscar_numeros(canal, id_cedente, nome_carteira)[0]

    def buscar_numeros_preventivo(
        self,
        id_cedente: int,
        canal: str,
        id_cedente_fallback: int = 100,
        nome_carteira: str | None = None,
    ):
        return self._buscar_numeros(canal, id_cedente, nome_carteira)

    def buscar_numeros(self, id_cedente: int, canal: str, nome_carteira: str | None = None):
        return self._buscar_numeros(canal, id_cedente, nome_carteira)
