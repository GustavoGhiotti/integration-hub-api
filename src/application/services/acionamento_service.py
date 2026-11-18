import ldap3
from src.infrastructure.repositories.sql_acionamento_repository import AcionamentoRepository
from src.shared.utils.env_load import *
from ldap3 import MODIFY_REPLACE


class AcionamentoService:
    def __init__(self):
        self.repo = AcionamentoRepository()

    def pesquisar(self, sala:str):
        if not sala:
            raise ValueError("sala obrigatoria")
        
        resultado =self.repo.pesquisar(sala)

        if not resultado:
            return None
        
        return resultado