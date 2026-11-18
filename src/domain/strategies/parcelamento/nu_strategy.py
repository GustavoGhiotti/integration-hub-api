from src.domain.entities import Divida
from src.application.services.collectsys.valores_dividas_service import ValoresDividas
from .base_strategy import ParcelamentoStrategy


class NuStrategy(ParcelamentoStrategy):
    async def gerar_propostas(self, contrato: Divida, id_contrato: int) -> list[Divida]:
        contrato.parcelamento_max = 1

        return await ValoresDividas.valores_parcelados(
            contrato,
            valor_min=None,
            valor_max=None,
            cartao_35=None,
        )