from src.domain.exceptions.collectsys_exception import RetornoTratadoBeta
from src.shared.utils import extrair_tag
from src.shared.utils.xml_tratamentos import gerar_xml_detalhe_calculo

from .default_rule import DefaultCedenteRule
from .types import AcordoDetalhe, RuleDecision


class BancoalfaCedenteRule(DefaultCedenteRule):
    def tratar_retorno(self, context):
        if "<RetornoErro>" not in context.resultado:
            return RuleDecision.retornar(context.resultado)

        if (
            "forma de negociacao" in context.resultado_normalizado
            and "forma de negociacao" not in context.detalhe_xml_normalizado
        ):
            context.detalhes.append(AcordoDetalhe("FORMA DE NEGOCIACAO", "RENEG", 2733))
            context.detalhe_xml = gerar_xml_detalhe_calculo(context.detalhes)
            return RuleDecision.recalcular()

        if "esse acordo nao tem opcao de parcelamento" in context.resultado_normalizado:
            return RuleDecision.retornar(context.resultado)

        if "<RetornoErro>" in context.resultado and "Retorno API" in context.resultado:
            produto = extrair_tag(context.xml_divida, "<Identificador>", "</Identificador>")
            if "ep" in (produto or "").lower():
                raise RetornoTratadoBeta("No momento cliente possui somente proposta a vista")

        return super().tratar_retorno(context)
