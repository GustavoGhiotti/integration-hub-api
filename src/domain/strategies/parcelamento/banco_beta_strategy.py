from src.domain.entities import Divida
from src.domain.entities.cedentes import BancoBeta
from src.infrastructure.external.collectsys import Calcular, ConsultaContratoDetalhe
from src.application.services.collectsys.valores_dividas_service import ValoresDividas
from src.shared.utils import extrair_tag
from src.domain.exceptions import CollectSysException
from .base_strategy import ParcelamentoStrategy


class BancoBetaParcelamentoStrategy(ParcelamentoStrategy):
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

        nm_produto = ConsultaContratoDetalhe(
            contrato.id_cliente,
            id_contrato,
        ).consultar_nm_produto()

        atraso = int(extrair_tag(contrato.xml, "<Atraso>", "</Atraso>") or 0)

        cartao_35 = None
        if BancoBeta.eh_produto_cartao(nm_produto) and atraso <= 35:
            cartao_35 = "SIM"

        retorno = calculo_parcelamento.calcular_acordo_com_detalhes(
            parcelado="VALOR ENTRADA",
            cartao_35=cartao_35,
        )

        if not isinstance(retorno, tuple) or len(retorno) != 5:
            raise CollectSysException(mensagem=str(retorno))

        valor_min, valor_max, parcela_min, parcela_max, cartao_35 = retorno

        contrato.parcelamento_max = parcela_max
        contrato.valor = valor_max

        propostas = await ValoresDividas.valores_parcelados(
            contrato,
            valor_min,
            valor_max,
            cartao_35,
        )

        for proposta in propostas:
            detalhe = BancoBeta.detalhe_proposta(
                nm_produto,
                proposta.qtd_parcelas,
                cartao_35,
            )
            if detalhe:
                proposta.detalhe_proposta = detalhe

        return propostas
