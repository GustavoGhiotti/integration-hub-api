from typing import Protocol

from src.domain.dtos.divida_ativa_dto import CedenteDividaDTO


class DividaAtivaGateway(Protocol):
    async def obter_por_cpf(self, cpf: str) -> list[CedenteDividaDTO]:
        ...