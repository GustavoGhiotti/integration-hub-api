from src.infrastructure.database.sql_server_connection import SQLServerConnection
from src.shared.utils.env_load import DB_66
import json
import datetime


class TemplateRepository:
    def __init__(self):
        self.db = SQLServerConnection(server=DB_66, database="DB_CHATBOT")

    def buscar_por_sid(self, sid_template: str):
        query = """
            SELECT 
                SID_TEMPLATE,
                NOME_TEMPLATE,
                LINGUA,
                CRIADO_EM,
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
            FROM TWILIO.TB_TEMPLATES WITH (NOLOCK)
            WHERE SID_TEMPLATE = ?
        """

        rows = self.db.execute(query=query, parametros=(sid_template,), fetch=True)
        if not rows:
            raise Exception(f"Template nÃo encontrado pelo SID '{sid_template}'.")

        row = rows[0]

        def parse_json(v):
            if not v:
                return None
            try:
                return json.loads(v)
            except:
                return None

        return {
            "sidTemplate": row["SID_TEMPLATE"],
            "nomeTemplate": row["NOME_TEMPLATE"],
            "variaveis": parse_json(row["VARIAVEIS"]),
            "tipos": parse_json(row["TIPOS"]),
            "corpos": parse_json(row["CORPOS"]),
            "acoes": parse_json(row["ACOES"]),
            "media": parse_json(row["MEDIA"]),
            "titulos": parse_json(row["TITULOS"]),
            "subtitulos": parse_json(row["SUBTITULOS"]),
            "statusAprovacao": row["STATUS_APROVACAO"],
            "motivoRejeicao": row["MOTIVO_REJEICAO"],
            "dataAprovacao": row["DATA_APROVACAO"],
        }

    def salvar_ou_atualizar(self, tpl: dict):
        criado_em = tpl.get("criado_em")
        data_aprov = tpl.get("data_aprovacao")

        if isinstance(criado_em, str):
            try:
                criado_em = datetime.fromisoformat(
                    criado_em.replace("Z", "").replace("+00:00", "")
                )
            except:
                criado_em = None

        if isinstance(data_aprov, str):
            try:
                data_aprov = datetime.fromisoformat(
                    data_aprov.replace("Z", "").replace("+00:00", "")
                )
            except:
                data_aprov = None

        query = """
            MERGE TWILIO.TB_TEMPLATES AS T
            USING (SELECT ? AS SID_TEMPLATE) AS SRC
            ON T.SID_TEMPLATE = SRC.SID_TEMPLATE
            
            WHEN MATCHED THEN 
                UPDATE SET
                    NOME_TEMPLATE = ?, 
                    LINGUA = ?, 
                    CRIADO_EM = ?,
                    VARIAVEIS = ?, 
                    TIPOS = ?, 
                    CORPOS = ?, 
                    ACOES = ?, 
                    MEDIA = ?,
                    TITULOS = ?, 
                    SUBTITULOS = ?,
                    STATUS_APROVACAO = ?, 
                    MOTIVO_REJEICAO = ?, 
                    DATA_APROVACAO = ?
            
            WHEN NOT MATCHED THEN 
                INSERT (
                        SID_TEMPLATE,
                        NOME_TEMPLATE,
                        LINGUA,
                        CRIADO_EM,
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
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """

        parametros = (
            tpl["sid_template"],
            tpl["nome_template"],
            tpl["lingua"],
            criado_em,
            json.dumps(tpl["variaveis"]),
            json.dumps(tpl["tipos"]),
            json.dumps(tpl["corpos"]),
            json.dumps(tpl["acoes"]),
            json.dumps(tpl["media"]),
            json.dumps(tpl["titulos"]),
            json.dumps(tpl["subtitulos"]),
            tpl.get("status_aprovacao"),
            tpl.get("motivo_rejeicao"),
            data_aprov,
            tpl["sid_template"],
            tpl["nome_template"],
            tpl["lingua"],
            criado_em,
            json.dumps(tpl["variaveis"]),
            json.dumps(tpl["tipos"]),
            json.dumps(tpl["corpos"]),
            json.dumps(tpl["acoes"]),
            json.dumps(tpl["media"]),
            json.dumps(tpl["titulos"]),
            json.dumps(tpl["subtitulos"]),
            tpl.get("status_aprovacao"),
            tpl.get("motivo_rejeicao"),
            data_aprov
        )

        self.db.execute(query=query, parametros=parametros)

    def buscar_todos_sids(self):
        query = "SELECT SID_TEMPLATE FROM TWILIO.TB_TEMPLATES WITH (NOLOCK)"
        rows = self.db.execute(query=query, fetch=True)
        return rows or []

    def buscar_ou_sincronizar_por_sid(self, sid_template: str, sync_service):
        try:
            return self.buscar_por_sid(sid_template)
        except Exception:
            sync_service.sincronizar_template_especifico(sid_template)
            return self.buscar_por_sid(sid_template)


class NumeroRepository:
    def __init__(self):
        self.db = SQLServerConnection(server=DB_66, database="DB_CHATBOT")

    def _map_numero_row(self, row):
        if isinstance(row, str):
            return {"numero": row, "serviceSid": None, "status": None, "cedente": None}
        if isinstance(row, (list, tuple)):
            return {
                "numero": row[0],
                "serviceSid": row[1] if len(row) > 1 else None,
                "status": row[2] if len(row) > 2 else None,
                "cedente": row[3] if len(row) > 3 else None,
            }
        return {
            "numero": row["NUMERO"],
            "serviceSid": row.get("SERVICE_SID"),
            "status": row.get("STATUS"),
            "cedente": row.get("CEDENTE"),
        }

    def _buscar_numeros(self, id_cedente: int, canal: str):
        query = """
            SELECT
                NUMERO,
                SERVICE_SID,
                STATUS,
                CEDENTE
            FROM twilio.tb_numeros WITH (NOLOCK)
            WHERE ID_CEDENTE = ?
            AND CANAL = ?
            AND UPPER(STATUS) IN ('MEDIUM', 'HIGH')
            ORDER BY CASE UPPER(STATUS) WHEN 'HIGH' THEN 0 ELSE 1 END, ID ASC
        """
        rows = self.db.execute(query=query, parametros=(id_cedente, canal), fetch=True)
        return [self._map_numero_row(row) for row in (rows or [])]

    def buscar_numero_preventivo(self, id_cedente: int, canal: str, id_cedente_fallback: int = 100):
        numeros = self._buscar_numeros(id_cedente, canal)
        if not numeros and id_cedente_fallback is not None:
            numeros = self._buscar_numeros(id_cedente_fallback, canal)
        if not numeros:
            raise Exception("Nenhum numero ativo encontrado para este cedente")
        return numeros[0]

    def buscar_numero(self, id_cedente: int, canal: str):
        numeros = self._buscar_numeros(id_cedente, canal)
        if not numeros:
            raise Exception("Nenhum numero ativo encontrado para este cedente")
        return numeros[0]

    def buscar_numeros_preventivo(self, id_cedente: int, canal: str, id_cedente_fallback: int = 100):
        numeros = self._buscar_numeros(id_cedente, canal)
        if not numeros and id_cedente_fallback is not None:
            numeros = self._buscar_numeros(id_cedente_fallback, canal)
        if not numeros:
            raise Exception("Nenhum numero ativo encontrado para este cedente")
        return numeros

    def buscar_numeros(self, id_cedente: int, canal: str):
        numeros = self._buscar_numeros(id_cedente, canal)
        if not numeros:
            raise Exception("Nenhum numero ativo encontrado para este cedente")
        return numeros
