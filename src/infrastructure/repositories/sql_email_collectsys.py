from src.infrastructure.database.sql_server_connection import SQLServerConnection
from src.shared.utils.env_load import DB_65


class EmailCliente:
    def __init__(self):
        self.db = SQLServerConnection(server=DB_65, database="easycollector")


    def busca_cliente_email(self, id_cliente: int):
        query = """
            SELECT [ID_CLIENTE]
                ,[ID_EMAIL]
                ,[NM_EMAIL]
                ,[TP_PREFERENCIAL]
            FROM easycollector.dbo.TB_CLIENTE_EMAIL
                where ID_CLIENTE = ?
        """

        parametros = (id_cliente,)
        
        dados = self.db.execute(query=query, parametros=parametros, fetch=True)
        return dados

    def troca_preferencia(self, preferencial: int, id_cliente:int, id_email: str):
        query = """
            UPDATE easycollector.dbo.TB_CLIENTE_EMAIL
            SET 
            TP_PREFERENCIAL = ?
            WHERE ID_CLIENTE = ?
            AND ID_EMAIL = ?
        """
        
        parametros = (preferencial, id_cliente, id_email)
        
        dados = self.db.execute(query=query, parametros=parametros, fetch=False)
        return dados
    
    def email_envio_boleto(self, id_cliente: int, nm_email:str):
        query = """
            INSERT INTO easycollector.dbo.TB_CLIENTE_EMAIL (
                ID_CLIENTE, 
                TP_EMAIL, 
                TP_ORIGEM, 
                TP_HABILITADO, 
                NM_EMAIL, 
                TP_PREFERENCIAL, 
                DT_INCLUSAO
            )
            VALUES (
                ?,
                0,
                0,
                1,
                ?,
                1,
                GETDATE()
            )
        """
        
        parametros = (id_cliente, nm_email)
        
        dados = self.db.execute(query=query, parametros=parametros, fetch=False)
        return dados
    
    def remover_email(self, id_cliente: int, nm_email: str):
        query = """
            DELETE easycollector.dbo.TB_CLIENTE_EMAIL
            WHERE ID_CLIENTE = ?
            AND NM_EMAIL = ?
        """

        parametros = (id_cliente, nm_email)
        
        dados = self.db.execute(query=query, parametros=parametros, fetch=False)
        return dados
