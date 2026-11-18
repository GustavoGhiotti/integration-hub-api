from dataclasses import dataclass
from . import BaseRequest

@dataclass
class ObterDividaCpfRequest(BaseRequest):
    cpf:str

@dataclass 
class ObterDividaIdRequest(BaseRequest):
    id_cliente:str




