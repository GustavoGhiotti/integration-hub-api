from src.infrastructure.database.sql_server_connection import SQLServerConnection
from src.shared.utils import env_load

class AuthAPI:
    def __init__(self):
        self.db = SQLServerConnection(server=env_load.DB_66,database="DB_API")

    def obter_token(self, token:str) -> list | None:
        query = f"""
                    OPEN SYMMETRIC KEY CERT_CRIPTOGRAFIA
                    DECRYPTION BY CERTIFICATE CERT_API_MASTER WITH PASSWORD = '{env_load.TOKEN_DB_API}'

                    SELECT TOP 1
                        USUARIO = CAST (DECRYPTBYKEY(USUARIO) AS varchar(MAX))
                        ,SENHA = CAST (DECRYPTBYKEY(SENHA) AS varchar(MAX))
                    FROM TB_TOKEN_USUARIO WITH(NOLOCK)
                    WHERE CAST (DECRYPTBYKEY(TOKEN_KEY) AS varchar(MAX)) = ?
                """

        parametros = [token]
        return self.db.execute(query=query,parametros=parametros,fetch=True)


class UserAPI:
    def __init__(self):
        self.db = SQLServerConnection(server=env_load.DB_66,database="DB_DESENVOLVIMENTO")

    def consultar(self, usuario:str, senha:str) -> list | None:
        query = """
                    OPEN SYMMETRIC KEY KEY_API_ACME
                    DECRYPTION BY CERTIFICATE CERT_API_ACME;

                    SELECT
                        ID,
                        CONVERT(VARCHAR(MAX), DecryptByKey(USERNAME)) AS USERNAME,
                        CONVERT(VARCHAR(MAX), DecryptByKey(PASSWORD)) AS PASSWORD,
                        ROTAS_PERMITIDAS,
                        PROVEDOR,
                        ATIVO,
                        ID_USUARIO_COLLECTSYS,
                        DT_REGISTRO
                    FROM [APIAcme].[TB_USUARIO] WITH(NOLOCK)
                    WHERE CONVERT(VARCHAR(MAX), DecryptByKey(USERNAME)) = ?
                    AND CONVERT(VARCHAR(MAX), DecryptByKey(PASSWORD)) = ?;

                    CLOSE SYMMETRIC KEY KEY_API_ACME;
                """

        params = (usuario, senha)
        result = self.db.execute(query=query,parametros=params, fetch=True)
        return result[0] if result else None
