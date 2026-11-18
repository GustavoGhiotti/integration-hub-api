from dataclasses import dataclass

from src.domain.models.base_request import BaseRequest

@dataclass
class EmitirBoletoRequest(BaseRequest):
    id_cliente:int
    id_acordo:int
    parcela:int


@dataclass
class EmitirBoletoOriginalRequest:
    id_cliente:int
    xml_divida:int
