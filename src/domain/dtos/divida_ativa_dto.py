from dataclasses import dataclass, field
from typing import Any, Literal

OrigemDivida = Literal["COLLECTSYS", "CREDO", "VCOM"]

@dataclass(slots=True, frozen=True)
class ContratoResumoDTO:
    id_contrato: int | str
    grupo: str
    contrato: str | None = None
    id_credor: int | None = None
    cpf_cnpj: str | None = None
    parcelas: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class AcordoResumoDTO:
    id_acordo: int
    grupo: str
    valor: float
    data_pagamento: str


@dataclass(slots=True)
class CedenteDividaDTO:
    origem: OrigemDivida
    cedente: str
    id_cedente: int
    id_cliente: int | str | None
    possui_divida_ativa: bool = True
    contratos: list[ContratoResumoDTO] = field(default_factory=list)
    acordos: list[AcordoResumoDTO] = field(default_factory=list)
