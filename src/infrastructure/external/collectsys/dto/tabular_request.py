from dataclasses import dataclass
from typing import Sequence

from . import BaseRequest


@dataclass(slots=True)
class TabularRequest(BaseRequest):
    id_cliente: int
    id_acao: int
    descricao_acao: str
    ddd: int
    telefone: int


@dataclass(slots=True)
class TabularComDetalhesRequest(TabularRequest):
    detalhes_xml: str


@dataclass(slots=True)
class TabularComDividaRequest(TabularComDetalhesRequest):
    divida_xml: str