from dataclasses import dataclass
from src.domain.models.base_request import BaseRequest
from src.shared.utils.data import validar_data_ymd

@dataclass
class FormalizarAcordoRequest(BaseRequest):
    id_cliente:int
    xml_acordo:str
