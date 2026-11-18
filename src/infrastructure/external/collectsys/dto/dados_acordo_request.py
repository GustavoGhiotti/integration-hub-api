from dataclasses import dataclass

from src.domain.models.base_request import BaseRequest

@dataclass
class DadosAcordoRequest(BaseRequest):
    id_cliente:int
    id_acordo:int
