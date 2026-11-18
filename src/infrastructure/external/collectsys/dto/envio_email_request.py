from dataclasses import dataclass

from src.domain.models.base_request import BaseRequest

@dataclass
class EnviarEmailRequest(BaseRequest):
    id_cliente:int
    id_acordo:int
    parcela:int
    email:str
