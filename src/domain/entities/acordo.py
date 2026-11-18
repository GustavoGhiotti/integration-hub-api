from pydantic import BaseModel
from datetime import date   

class Acordo(BaseModel):
    id_cedente: int
    nome_cedente: str
    id_cliente:int
    id_acordo: int
    id_contrato: int
    valor: float
    numero_parcelas: int
    vencimento_boleto: date
    situacao_acordo: str
    xml:str
