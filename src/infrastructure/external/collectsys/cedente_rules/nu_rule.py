from datetime import date, timedelta

from src.shared.utils.data import validacao_dia_util

from .default_rule import DefaultCedenteRule


class NuCedenteRule(DefaultCedenteRule):
    cedente_ids = (14,)

    def definir_data_vencimento(self, context):
        data_maxima = validacao_dia_util(date.today() + timedelta(days=2))
        data_solicitada = context.vencimento or data_maxima
        context.vencimento = min(data_solicitada, data_maxima)
        context.data_vencimento = validacao_dia_util(context.vencimento)

    def montar_xml_divida_calcular_acordo(self, calcular, parcelado: str = "") -> str:
        quantidade_parcelas = self._quantidade_parcelas_condicao(getattr(calcular, "condicao", None))
        maior_numero_prestacao = self._maior_numero_prestacao(calcular.xml_divida)
        if (
            quantidade_parcelas is not None
            and maior_numero_prestacao is not None
            and quantidade_parcelas >= maior_numero_prestacao
        ):
            return calcular.xml_divida

        return self.filtrar_xml_divida_por_condicao(calcular)
