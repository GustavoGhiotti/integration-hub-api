import os
import smbclient
from dotenv import load_dotenv
from typing import BinaryIO
from io import BufferedReader
import subprocess
import time
import smbprotocol.exceptions

_BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
_ENV_PATH = os.path.join(_BASE_DIR, ".env")
load_dotenv(_ENV_PATH)

SERVIDOR_94 = os.getenv("SERVIDOR_94")
USER_ROBO = os.getenv("USUARIO_SERVIDOR")
SENHA_ROBO = os.getenv("SENHA_ROBO")


class ConexaoServidor:
    def __init__(self, servidor:str, usuario:str, senha:str):
        self._servidor = servidor
        self._usuario = usuario
        self._senha = senha

class Servidor(ConexaoServidor):
    def __init__(self, servidor:str, usuario:str, senha:str):
        super().__init__(servidor, usuario, senha)

    def conectar(self) -> None:
        smbclient.register_session( server=self._servidor,
                                    username=self._usuario,
                                    password=self._senha
                                    )   
    
    def mover(self, carga: bytes, destino: BinaryIO) -> None:
        destino.write(carga)
        destino.close()


    def gerar_caminho_destino(self, caminho:str) -> BinaryIO: 
        return smbclient.open_file(caminho, mode="wb")
   

    def listar_arquivos(self, caminho:str) -> list:
        return smbclient.listdir(caminho)
    
    def abrir_arquivo(self, caminho:str) -> BufferedReader:
        return smbclient.open_file(caminho, mode="rb")
    
    def remover(self, caminho: str):
        smbclient.remove(caminho)

    def remover_com_retry(self, caminho, tentativas=20, intervalo=0.05):
        for _ in range(tentativas):
            try:
                return self.remover(caminho)  # tenta remover
            except smbprotocol.exceptions.SMBOSError:
                time.sleep(intervalo)  # espera e tenta de novo
        raise RuntimeError(f"Não foi possível remover o arquivo após {tentativas} tentativas: {caminho}")

    

class ServidorSO(ConexaoServidor):
    def __init__(self, servidor:str, usuario:str, senha:str, letra:str):
        super().__init__(servidor, usuario, senha)
        self.letra = letra
        self.__conectar()

    def __conectar(self):
        if not self.__verifica_conexao():
            subprocess.run([
                "net", "use", f"{self.letra}:", fr"\\{self._servidor}\easycollector",
                fr"/user:{self._usuario}", self._senha
            ], check=True)

    def __verifica_conexao(self) -> bool:
        resultado = subprocess.run(["net", "use"], capture_output=True, text=True)
        saida = resultado.stdout.lower()

        letra = self.letra.lower() + ":"
        servidor = self._servidor.lower().replace("\\", "")

        for linha in saida.splitlines():
            if letra in linha and servidor in linha:
                return True
            
        return False
    

    def copiar_arquivo():
        pass

    def copiar_arquivo_grande():
        pass


class SMBConexao:
    def __init__(self):
        self.servidor = Servidor(SERVIDOR_94, USER_ROBO, SENHA_ROBO)
        self.servidor.conectar()

    def caminho94(self):
        return r"\\10.0.0.94\c$\inetpub\wwwroot\ApiGrupoAcme\boleto\.cliente"

    def caminho64(self):
        return self.caminho94()
    
