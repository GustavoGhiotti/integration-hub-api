from dataclasses import dataclass

from src.domain.models.base_request import BaseRequest

@dataclass
class ConsultarContratoRequest(BaseRequest):
    id_cliente:int
    id_contrato:int
