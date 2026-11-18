import re
import time

from src.domain.exceptions.collectsys_exception import NenhumaDividaException, RetornoTratadoBeta
from src.shared.utils import (
    capturar_intervalo_parcelamento,
    capturar_parcelamento_max,
    extrair_tag,
    tratativa_palavra,
)
from src.shared.utils.xml_tratamentos import gerar_xml_detalhe_calculo

from .base import BetaLikeCedenteRule
from .types import RuleDecision


class TetaSwatCedenteRule(BetaLikeCedenteRule):
    MENSAGEM_SEM_DIVIDA = "No momento, nÃo constam dÃ­vidas ativas do cliente em nossa assessoria."

    def montar_xml_divida_calcular_acordo(self, calcular, parcelado: str = "") -> str:
        return self._marcar_todas_dividas(calcular.xml_divida)

    def montar_xml(self, context):
        context.xml_divida = self._marcar_todas_dividas(context.xml_divida)
        super().montar_xml(context)
        context.desconto = 100

    def tratar_retorno(self, context):
        if self._eh_contrato_nao_encontrado(context):
            raise NenhumaDividaException(self.MENSAGEM_SEM_DIVIDA)

        if "<RetornoErro>" not in context.resultado:
            if "VALOR ENTRADA" in context.parcelado:
                return RuleDecision.retornar(self._montar_retorno_parcelamento(context))
            if context.valido:
                return RuleDecision.retornar(context.resultado)
            raise RetornoTratadoBeta(
                "Calculo invalido para o cedente TETA SWAT. O CollectSys retornou um acordo sem parcelas validas."
            )

        if "oferta possui um ou mais contratos com acordo" in context.resultado_normalizado:
            raise RetornoTratadoBeta("Cliente ja possui acordo fora de nossa acessoria")

        if "VALOR ENTRADA" in context.parcelado:
            parcelamento_min, parcelamento_max_intervalo = capturar_intervalo_parcelamento(context.resultado)
            parcelamento_max = capturar_parcelamento_max(context.resultado)
            if parcelamento_max_intervalo is not None:
                parcelamento_max = parcelamento_max_intervalo
            if parcelamento_min is not None:
                context.parcelamento_min = parcelamento_min
            if parcelamento_max is not None:
                context.parcelamento_max = parcelamento_max
            return RuleDecision.retornar(self._montar_retorno_parcelamento(context))

        if "plano minimo" in context.resultado_normalizado:
            return RuleDecision.retornar(context.resultado_tratado)

        if "<mensagem>nenhuma" in context.resultado.lower() and "divida foi informada" in context.resultado_normalizado:
            return RuleDecision.retornar(context.resultado)

        if tratativa_palavra(context.resultado, "%NEGOCIACAO MEIO PAGAMENTO%"):
            time.sleep(1)
            return RuleDecision.recalcular()

        if tratativa_palavra(context.resultado, "%Retorno WS%"):
            time.sleep(1)
            context.detalhe_xml = gerar_xml_detalhe_calculo(context.detalhes)
            return RuleDecision.recalcular()

        return None

    def finalizar_falha(self, context):
        if self._eh_contrato_nao_encontrado(context):
            raise NenhumaDividaException(self.MENSAGEM_SEM_DIVIDA)
        raise RetornoTratadoBeta(context.resultado_tratado)

    def _eh_contrato_nao_encontrado(self, context) -> bool:
        mensagem = f"{context.resultado_normalizado} {context.resultado_tratado_normalizado}"
        return "nao foi encontr" in mensagem and "contrato" in mensagem

    def _marcar_todas_dividas(self, xml_divida: str) -> str:
        return re.sub(
            r"<Marcado>\s*false\s*</Marcado>",
            "<Marcado>true</Marcado>",
            xml_divida or "",
            flags=re.IGNORECASE,
        )

    def _montar_retorno_parcelamento(self, context):
        valor_parcela = extrair_tag(context.resultado, "<ValorParcela>", "</ValorParcela>")
        if valor_parcela is not None:
            valor_parcela = float(str(valor_parcela).replace(",", "."))

        valor_base = valor_parcela if valor_parcela is not None else context.valor_entrada or 0
        parcela_min = context.parcelamento_min or 1
        parcela_max = context.parcelamento_max or int(context.plano or 1)
        return (valor_base, valor_base, parcela_min, parcela_max, context.cartao_35)
