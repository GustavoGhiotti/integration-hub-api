from src.infrastructure.servers.conexao import SMBConexao

class Servidores(SMBConexao):
    def __init__(self):
        super().__init__()
    
    
    def caminho94(self):
        #Caminho compartilhado.
        return r"\\10.0.0.94\c$\inetpub\wwwroot\ApiGrupoAcme\boleto\\.cliente\\"