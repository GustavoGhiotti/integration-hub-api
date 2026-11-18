from abc import ABC, abstractmethod
from src.domain.entities import Divida


class ParcelamentoStrategy(ABC):
    @abstractmethod
    async def gerar_propostas(self, contrato: Divida, id_contrato: int) -> list[Divida]:
        pass