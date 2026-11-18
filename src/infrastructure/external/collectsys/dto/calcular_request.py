from dataclasses import dataclass
from src.shared.utils.data import validar_data_ymd
from . import BaseRequest

@dataclass
class CalcularAcordoRequest(BaseRequest):
    id_cliente:int
    plano:int
    data:str
    entrada:float
    desconto:int
    xml_divida:str
    
    def __post_init__(self):
        self.data = validar_data_ymd(self.data)

@dataclass 
class CalcularAcordoDetalheRequest(CalcularAcordoRequest):
    xml_detalhe:str

@dataclass
class CalcularDividaRequest(BaseRequest):
    id_cliente:int
    xml_divida:str


