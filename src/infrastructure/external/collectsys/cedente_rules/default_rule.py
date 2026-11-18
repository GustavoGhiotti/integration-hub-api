import time

from src.shared.utils import tratativa_palavra
from src.shared.utils.data import capturar_data
from src.shared.utils.xml_tratamentos import capturar_valor, forcar_detalhe_vazio, gerar_xml_detalhe_calculo

from .base import BaseCedenteRule
from .types import RuleDecision


class DefaultCedenteRule(BaseCedenteRule):
    def montar_xml(self, context):
        match context.id_cedente:
            case 51:
                context.desconto = 100
                detalhes = [
                    ["SIMULATION_ID", "", 1292, "Acordo", "Manual"],
                    ["IOF_ACORDO", "", 743, "Acordo", "Manual"],
                    ["TIPO PAGAMENTO BANCOALFA", "BOLETO", 2812, "Acordo", "Manual"],
                ]

            case 65 | 73:
                context.desconto = 200
                detalhes = [
                    ["TIPO PAGAMENTO DELTA", "BOLETO", 2805, "Acordo", "Manual"],
                    ["VALOR INTEGRAL PARCELA", "", 1237, "Acordo", "Manual"],
                    ["VALOR DESCONTO PARCELA", "", 1238, "Acordo", "Manual"],
                    ["VALOR MINIMO POLITICA", "", 1239, "Acordo", "Manual"],
                ]

            case 70:
                context.desconto = 0
                detalhes = [["TIPO PAGAMENTO RETURN", "BOLETO", 2720, "Acordo", "Manual"]]

            case 83 | 90 | 77 | 103:
                context.desconto = 200
                detalhes = [
                    ["OFFER ID", "", 2762, "Acordo", "Manual"],
                    ["TIPO PAGAMENTO PARCELAS", "BOLETO", 2771, "Acordo", "Manual"],
                    ["TIPO PAGAMENTO ENTRADA", "BOLETO", 2770, "Acordo", "Manual"],
                ]

            case _:
                context.desconto = 100
                detalhes = []

        self.definir_data_vencimento(context)
        self.atualizar_detalhes(context, detalhes)

    def tratar_retorno(self, context):
        if "<RetornoErro>" not in context.resultado:
            return RuleDecision.retornar(context.resultado)

        if "data" in context.resultado_normalizado:
            nova_data = capturar_data(context.resultado)
            if nova_data:
                context.data_vencimento = nova_data
                return RuleDecision.recalcular()

            logger = context._get_method_logger("calcular_acordo_com_detalhes")
            logger.warning(
                "capturar_data_sem_match id_cliente=%s id_cedente=%s plano=%s",
                context.id_cliente,
                context.id_cedente,
                context.plano,
            )

        elif "valor" in context.resultado_normalizado:
            novo_valor = capturar_valor(context.resultado)
            if novo_valor is not None:
                context.valor_entrada = novo_valor
                return RuleDecision.recalcular()

        elif "<mensagem>nenhuma" in context.resultado.lower() and "divida foi informada" in context.resultado_normalizado:
            return RuleDecision.retornar(context.resultado)

        elif tratativa_palavra(context.resultado, "%NEGOCIACAO MEIO PAGAMENTO%"):
            time.sleep(1)
            return RuleDecision.recalcular()

        elif tratativa_palavra(context.resultado, "%Retorno WS%"):
            time.sleep(1)
            context.detalhe_xml = gerar_xml_detalhe_calculo(
                detalhes=context.detalhes,
                force_empty=forcar_detalhe_vazio(context.id_cedente, context.detalhes),
            )
            return RuleDecision.recalcular()

        return None
