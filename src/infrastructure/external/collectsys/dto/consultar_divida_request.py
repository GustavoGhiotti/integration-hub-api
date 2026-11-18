from dataclasses import dataclass

from src.domain.models.base_request import BaseRequest

@dataclass
class ConsultaDividaDetalheRequest(BaseRequest):
    id_cliente:int
    id_contrato:int
    id_divida:int
