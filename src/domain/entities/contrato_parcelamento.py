from dataclasses import dataclass
from src.shared.utils.xml_tratamentos import *
from typing import Optional
from datetime import date

@dataclass
class ParcelamentoDivida:
    nome_cedente:str
    id_cedente:int
    id_cliente:int
    id_contrato:list
    xml:str
