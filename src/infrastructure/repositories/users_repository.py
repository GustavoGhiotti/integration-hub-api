from src.infrastructure.database.sql_server_connection import SQLServerConnection
from src.shared.utils import env_load


class Users_Repository:
    def __init__(self):

        self.db = SQLServerConnection(server=env_load.DB_66,database="DB_DESENVOLVIMENTO")
    def pesquisar(self, username:str, password:str):
        
        usuario = f'''SELECT ID, USERNAME, ATIVO, VEGA FROM  APIAcme.TB_LOGIN_MENSAGENS
                            WHERE USERNAME = ?
                            and PASSWORD  COLLATE Latin1_General_BIN2 = ?
                            '''   
        
        rows = self.db.execute(query=usuario, parametros=(username,password), fetch=True)

        if not rows:
            return None   
        
        row = rows[0] 

        return {
                "id": row["ID"],
                "username": row["USERNAME"],
                "is_active": row["ATIVO"],
                "VEGA": row["VEGA"]
            }


    def salvar_token(self,usuario_id:str,token_hash:str,):
        sql = f'''

                INSERT INTO TB_RECUPERACAO_SENHA (USUARIO_ID, TOKEN_HASH, EXPIRA_EM)
                SELECT top 1
                    ?,
                    ?,
                     DATEADD(MINUTE, 15, SYSUTCDATETIME())
                FROM APIAcme.TB_LOGIN_MENSAGENS
                            '''   
        
        self.db.execute(query=sql, parametros=(usuario_id,token_hash))

        return {
                "status":"ok"              
            }



    def buscar_usuario_por_email(self,email:str):
        sql = f'''SELECT ID from APIAcme.TB_LOGIN_MENSAGENS
                            WHERE EMAIL = ?
                            '''   
        
        rows = self.db.execute(query=sql, parametros=(email), fetch=True)

        if not rows:
            return None   
        
        row = rows[0] 

        return {
                "id": row["ID"]
            }
    

    def buscar_token_valido(self,usuario_id:str,token_hash:str):
        sql = f'''
        select TOKEN_HASH from TB_RECUPERACAO_SENHA 
        where USUARIO_ID = ?
        and  TOKEN_HASH = ?
        AND USADO = 0
        AND EXPIRA_EM >= SYSUTCDATETIME();
                            '''   
        
        rows = self.db.execute(query=sql, parametros=(usuario_id,token_hash), fetch=True)

        if not rows:
            return None  
        
        return {
                "sucesso":"ok" 
            }
    

    def buscar_token_valido_por_email(self,email:str,token_hash:str):
        sql = f'''
        select USUARIO_ID from TB_RECUPERACAO_SENHA 
        where USUARIO_ID =  (select ID from APIAcme.TB_LOGIN_MENSAGENS where EMAIL = ?)
        and  TOKEN_HASH = ?
                            '''   
        
        rows = self.db.execute(query=sql, parametros=(email,token_hash), fetch=True)

        if not rows:
            return None   
        
        row = rows[0] 

        return {
                "id": row["USUARIO_ID"]
            }
        

    
    def atualizar_senha_usuario(self,nova_senha:str,email:str):
        sql = f'''UPDATE APIAcme.TB_LOGIN_MENSAGENS 
                    SET PASSWORD = ?
                    WHERE  EMAIL = ?
                            '''   
        
        rows = self.db.execute(query=sql, parametros=(nova_senha,email))



        return {
                "status": "ok"
            }




    def marcar_token_como_usado(self,id:str):
        sql = f'''
        UPDATE TB_RECUPERACAO_SENHA 
        set USADO = 1
        where USUARIO_ID = ?
                            '''   
        
        rows = self.db.execute(query=sql, parametros=(id))


        return {
        "status": "ok"            
}

