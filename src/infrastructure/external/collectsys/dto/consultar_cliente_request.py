from dataclasses import dataclass

from src.domain.models.base_request import BaseRequest

@dataclass
class ConsultarClienteRequest(BaseRequest):
    id_cliente:int
