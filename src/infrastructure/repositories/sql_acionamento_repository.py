from src.infrastructure.database.sql_server_connection import SQLServerConnection
from src.shared.utils import env_load


class AcionamentoRepository:
    def __init__(self):

        self.db = SQLServerConnection(server=env_load.DB_66,database="DB_CHATBOT")
    def _buscar(self, tabela, NUMERO_DESTINO, NUMERO_ORIGEM, ID_CONVERSA, DATA_ENVIO):

        if NUMERO_DESTINO and NUMERO_ORIGEM:
            sql = f"""
                SELECT *
                FROM {tabela}
                WHERE 
                    (NUMERO_DESTINO = ? OR NUMERO_ORIGEM = ?)
                    AND CAST(DATA_ENVIO AS DATE) = ?
                ORDER BY DATA_ENVIO
            """
            params = (NUMERO_DESTINO, NUMERO_ORIGEM, DATA_ENVIO)

        else:
            sql = f"""
                SELECT *
                FROM {tabela}
                WHERE 
                    CAST(DATA_ENVIO AS DATE) = ?
                    AND ID_CONVERSA in (select ID_CONVERSA from {tabela}
                where CPF = ?)
                ORDER BY DATA_ENVIO
            """
            params = (DATA_ENVIO, ID_CONVERSA)

        return self.db.execute(query=sql, parametros=params, fetch=True)

    
    def pesquisar(self, NUMERO_DESTINO, NUMERO_ORIGEM, ID_CONVERSA, DATA_ENVIO, USUARIO):

        tabela = self._resolver_tabela(USUARIO)

        conversa = self._buscar(
            tabela,
            NUMERO_DESTINO,
            NUMERO_ORIGEM,
            ID_CONVERSA,
            DATA_ENVIO
        )

        return {
            "conversa": conversa
        }



    def busca(self, tabela, NUMERO_DESTINO, NUMERO_ORIGEM, ID_CONVERSA):

        if NUMERO_DESTINO and NUMERO_ORIGEM:
            sql = f"""
                SELECT DISTINCT CAST(DATA_ENVIO AS DATE) AS DATA_ENVIO
                FROM {tabela}
                WHERE (NUMERO_DESTINO = ? OR NUMERO_ORIGEM = ?)
                ORDER BY DATA_ENVIO
            """
            params = (NUMERO_DESTINO, NUMERO_ORIGEM)

        else:
            sql = f"""
                SELECT DISTINCT CAST(DATA_ENVIO AS DATE) AS DATA_ENVIO
                FROM {tabela}
                WHERE ID_CONVERSA in (select ID_CONVERSA from {tabela}
                where CPF = ?)
                ORDER BY DATA_ENVIO
            """
            params = (ID_CONVERSA,)

        return self.db.execute(query=sql, parametros=params, fetch=True)

    

    def salas(self, NUMERO_DESTINO, NUMERO_ORIGEM, ID_CONVERSA, USUARIO):

        tabela = self._resolver_tabela(USUARIO)

        info_rows = self.busca(
            tabela,
            NUMERO_DESTINO,
            NUMERO_ORIGEM,
            ID_CONVERSA
        )

        if not info_rows:
            return None

        return {
            "sala": info_rows
        }

    def _resolver_tabela(self, USUARIO):
        if USUARIO == "true":
            return "[DB_CHATBOT].twilio.TB_MENSAGENS_VEGA"
        return "[DB_CHATBOT].twilio.TB_MENSAGENS"






class PortalAcordoRepository:
    def __init__(self):
        self.db = SQLServerConnection(server=env_load.DB_66,database="DB_PORTALACORDO")
    def _buscar(self, ID_CONVERSA):

            sql = f"""
                SELECT *
                FROM [dbo].[TB_CHAT_MENSAGENS]
                WHERE 
                    CONVERSATION_SID = ?
                ORDER BY DT_CRIACAO
            """
            params = (ID_CONVERSA,)

            return self.db.execute(query=sql, parametros=params, fetch=True)

    
    def pesquisar(self, ID_CONVERSA):

        conversa = self._buscar(
            ID_CONVERSA,
        )

        return {
            "conversa": conversa
        }



    def busca(self, FILA, DATA, ATENDENTE):

        sql = f"""
					            SELECT Distinct  M.CONVERSATION_SID
            FROM [dbo].[TB_CHAT_MENSAGENS] M
            WHERE 
                 EXISTS(
				SELECT 1 FROM  [dbo].[TB_CHAT_MENSAGENS] X
				 WHERE X.CONVERSATION_SID = M.CONVERSATION_SID
      AND X.FILA = ?
				)
                AND CAST(DT_CRIACAO AS DATE) = ?
                AND  EXISTS(
				SELECT 1 FROM  [dbo].[TB_CHAT_MENSAGENS] X
				 WHERE X.CONVERSATION_SID = M.CONVERSATION_SID
      AND X.IDENTIFY = ?
				)
        """
        params = (FILA, DATA, ATENDENTE)

        return self.db.execute(query=sql, parametros=params, fetch=True)

    
    def salas(self, FILA, DATA, ATENDENTE):


        info_rows = self.busca(
            FILA,
            DATA,
            ATENDENTE
        )

        if not info_rows:
            return None

        return {
            "sala": info_rows,
        }



    def atendimento(self,):

        sql = """
            SELECT DISTINCT IDENTIFY
            FROM [dbo].[TB_CHAT_MENSAGENS]
            WHERE IDENTIFY NOT LIKE 'CH%'
            AND IDENTIFY NOT LIKE 'web_%'
        """

        lista = self.db.execute(query=sql, parametros=(), fetch=True)

        if not lista:
            return None
        return{
            "atendentes": lista
        }

         









