from src.infrastructure.database.sql_server_connection import SQLServerConnection
from src.shared.utils.env_load import TOKEN_DB_API


class SqlCollectSysRepository:
    def __init__(self, server:str, database:str):
        self.db = SQLServerConnection(server=server, database=database)
        self.key_api = TOKEN_DB_API

    def obter_usuario_collectsys(self, id_usuario:int):
        query = """
                    SELECT 
                        B.USUARIO AS USUARIO, 
                        B.SENHA AS SENHA 
                    FROM APIAcme.TB_USUARIO AS A WITH(NOLOCK)
                    JOIN APIAcme.TB_USUARIO_COLLECTSYS AS B WITH(NOLOCK) 
                        ON A.ID_USUARIO_COLLECTSYS = B.ID
                    WHERE A.ID = ? 
                """
        
        parametros = (id_usuario)
        
        dados = self.db.execute(query=query, parametros=parametros, fetch=True)
        return dados[0]
    

    def obter_usuario_cedente(self, id_usuario:int):
        query = """
                    SELECT 
                        USUARIO,
                        SENHA 
                    FROM APIACME.TB_USUARIO_COLLECTSYS WITH(NOLOCK)
                    WHERE ID = ?
                """
        
        parametros = (id_usuario)
        
        dados = self.db.execute(query=query, parametros=parametros, fetch=True)
        return dados[0]