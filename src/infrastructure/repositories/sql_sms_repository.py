import json
import logging
from datetime import datetime
from src.infrastructure.database.db_utils import safe_db_exec
from src.infrastructure.database.sql_server_connection import SQLServerConnection
from src.shared.utils.env_load import *

log = logging.getLogger("sms_sql")

class SqlSmsRepository:
    """
    Opera na base DB_CHATBOT do servidor 66.
    Tabela: sinch.TB_REGISTRO_SMS
    """
    def __init__(self):
        self.db = SQLServerConnection(server=DB_66, database="DB_CHATBOT")

    @safe_db_exec("SMS - registrar_disparo")
    def registrar_disparo(self, campanha: str, numero: str, mensagem:str) -> int:
        query = """
                    INSERT INTO sinch.TB_REGISTRO_SMS
                        (CAMPANHA, NUMERO_DESTINATARIO, CONTEUDO_SMS, DATA_ENVIO, STATUS_ENVIO, DETALHE_STATUS)
                    VALUES (?, ?, ?, ?, ?, ?)
                """
        params = (campanha, numero, mensagem, datetime.now(), 1, "enviado")
        return self.db.execute(query=query,parametros=params)

    @safe_db_exec("SMS - atualizar_status_por_msgid")
    def atualizar_status_por_msgid(self, message_id: str, status_bin: int, status_texto: str) -> int:
        query = """
                    UPDATE sinch.TB_REGISTRO_SMS
                        SET STATUS_ENVIO = ?, DETALHE_STATUS = ?, DATA_ATUALIZACAO = ?
                    WHERE MESSAGE_ID = ?
                """
        params = (status_bin, status_texto, datetime.now(), message_id)
        return self.db.execute(query=query,parametros=params)

    @safe_db_exec("SMS - inserir_delivery_se_nao_existir")
    def inserir_delivery_se_nao_existir(self, *, campanha: str, numero: str, conteudo: str,
                                        status_bin: int, status_texto: str, message_id: str) -> int:
        query = """
                    INSERT INTO sinch.TB_REGISTRO_SMS
                        (CAMPANHA, NUMERO_DESTINATARIO, CONTEUDO_SMS, DATA_ENVIO, STATUS_ENVIO, DETALHE_STATUS, MESSAGE_ID)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """
        params = (campanha, numero, conteudo, datetime.now(), status_bin, status_texto, message_id)       
        return self.db.execute(query=query,parametros=params)

    @safe_db_exec("SMS - registrar_resposta")
    def registrar_resposta(self, message_id: str, conteudo: str) -> int:
        query = """
            UPDATE sinch.TB_REGISTRO_SMS
               SET RESPOSTA_CLIENTE = ?, DATA_RESPOSTA = ?
             WHERE MESSAGE_ID = ?
        """
        params = (conteudo, datetime.now(), message_id)
        return self.db.execute(query=query,parametros=params)

    @safe_db_exec("SMS - salvar_raw")
    def salvar_raw(self, headers: dict | str, body: dict | str) -> int:
        """
        Armazena o conteúdo bruto do callback (headers + body) na tabela SINCH.TB_REGISTRO_SMS_RAW.
        """
        query = """
            INSERT INTO sinch.TB_REGISTRO_SMS_RAW 
                (HEADERS, BODY, DATA_RECEBIMENTO)
                VALUES (?, ?, GETDATE())
        """

        # Garante que headers e body fiquem em formato JSON válido
        headers_json = headers if isinstance(headers, str) else json.dumps(headers, ensure_ascii=False)
        body_json = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)

        params = (headers_json, body_json)
        return self.db.execute(query=query,parametros=params)


class SqlSmsInfobipRepository:
    def __init__(self):
        self.db = SQLServerConnection(server=DB_66, database="DB_SMS")

        
    def salvar_lote(self, batch):
        query = """
        INSERT INTO infobip.TB_WEBHOOK (
            ID_MENSAGEM,
            [TO],
            DT_ENVIO,
            DT_ENTREGA,
            STATUS,
            STATUS_DESC,
            VALOR,
            ERRO,
            RAW_JSON,
            DT_REGISTRO
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE())
        """

        parametros = [
            (
                job["id_msg"],
                job["enviado_para"],
                job["hora_envio"],
                job["entrega_msg"],
                job["status"],
                job["status_desc"],
                job["valor_sms"],
                job["erro"],
                json.dumps(job["raw_json"], ensure_ascii=False)
            )
            for job in batch
        ]

        self.db.executemany(query, parametros)