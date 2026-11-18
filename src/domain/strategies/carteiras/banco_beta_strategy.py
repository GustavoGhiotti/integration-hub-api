from src.domain.strategies.carteiras.base_strategy import CarteiraBaseStrategy, RetornoCarteiraBase
from datetime import date, timedelta
from dataclasses import dataclass


class BetaStrategy(CarteiraBaseStrategy):
    async def gerar_propostas(self, contrato: Divida, id_contrato: int) -> list[Divida]:
        calculo_parcelamento = Calcular(
            contrato.nome_cedente,
            contrato.id_cliente,
            contrato.id_cedente,
            min(contrato.parcelamento_max, 36),
            contrato.valor,
            contrato.xml,
            contrato.data_pagamento,
        )
