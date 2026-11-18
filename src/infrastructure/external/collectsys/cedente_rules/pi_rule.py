from src.infrastructure.external.collectsys.consulta_contrato_detalhe import ConsultaContratoDetalhe
from src.infrastructure.external.collectsys.providers.consulta_divida import ConsultaDividaDetalhe
from src.shared.utils.xml_tratamentos import extrair_array, extrair_tag, normalizar_nome

from .default_rule import DefaultCedenteRule
from .types import RuleDecision


class PiCedenteRule(DefaultCedenteRule):
    POLITICA_A_VISTA = "POLITICA A VISTA_V21"
    POLITICA_DIVIDA_ATE_2500 = "CAMPANHA ENTRADA R$50,00_V24"
    POLITICA_DIVIDA_ATE_4000 = "CAMPANHA ENTRADA R$100,00_VS 16_06_26"
    POLITICA_PADRAO = "5% ENTRADA SEM JUROS_V22"

    def consultar_contexto_produto(self, id_cliente: int, id_contrato: int):
        # A divida da PI traz sempre "PI" em NmProduto. O nome real do
        # produto (ex.: "CARTAO PALMEIRAS ELO MAIS") esta no detalhe do contrato.
        produto = ConsultaContratoDetalhe(id_cliente, id_contrato).consultar_produto_pi()
        if not produto:
            return None

        return {"produto": produto, "informativo": False}

    def montar_xml(self, context):
        context.desconto = 200
        self.definir_data_vencimento(context)
        detalhes = getattr(context, "pi_detalhes_consulta", None)
        if detalhes is None:
            detalhes = self._detalhes_pi(context)
        self.atualizar_detalhes(context, detalhes)

    def _detalhes_pi(self, context):
        politica = self._politica_negociacao(context)
        return [
            ["MEIO DE PAGAMENTO", "BOLETO_PIX", 1000, "Acordo", "Manual"],
            ["TIPO NEGOCIACAO", "ACORDO", 912, "Acordo", "Manual"],
            ["POLITICA NEGOCIACAO", politica, 1065, "Acordo", "Manual"],
            ["TIPO DE ENVIO DESCONTO", "ENVIAR MORA E PRINCIPAL", 1002, "Acordo", "Manual"],
            ["SEGURO PRESTAMISTA", "NAO", 2779, "Acordo", "Manual"],
        ]

    def _detalhes_consulta_divida(self, context):
        consulta_divida = ConsultaDividaDetalhe(
            context.id_cliente,
            context.xml_divida,
            context.id_cedente,
        ).consultar_divida()
        produto = consulta_divida[0][0]
        tipo = consulta_divida[0][1]
        return [
            ["MEIO DE PAGAMENTO", tipo, 1000, "Acordo", "Manual"],
            ["TIPO NEGOCIACAO", "ACORDO", 912, "Acordo", "Manual"],
            ["POLITICA NEGOCIACAO", produto, 1065, "Acordo", "Manual"],
            ["TIPO DE ENVIO DESCONTO", "ENVIAR MORA E PRINCIPAL", 1002, "Acordo", "Manual"],
            ["SEGURO PRESTAMISTA", "NAO", 2779, "Acordo", "Manual"],
        ]

    def _politica_negociacao(self, context):
        if int(context.plano or 1) == 1:
            return self.POLITICA_A_VISTA

        valor_original = self._valor_original_dividas(context.xml_divida)
        if valor_original <= 2500:
            return self.POLITICA_DIVIDA_ATE_2500
        if valor_original <= 4000:
            return self.POLITICA_DIVIDA_ATE_4000
        return self.POLITICA_PADRAO

    def _valor_original_dividas(self, xml_divida: str) -> float:
        xml_restante = xml_divida or ""
        total = 0.0

        while "<DividaAtiva>" in xml_restante:
            divida = extrair_array(xml_restante, "<DividaAtiva>", "</DividaAtiva>")
            if not divida:
                break

            total += self._valor_original_divida(divida)
            xml_restante = xml_restante.replace(divida, "", 1)

        return total

    def _valor_original_divida(self, divida: str) -> float:
        for tag in ("ValorDividaIntegral", "ValorDividaOriginalNovacao", "ValorDividaCalculo"):
            valor = extrair_tag(divida, f"<{tag}>", f"</{tag}>")
            if not valor:
                continue

            valor_convertido = self._converter_valor(valor)
            if valor_convertido > 0:
                return valor_convertido

        return 0.0

    def _converter_valor(self, valor: str) -> float:
        valor = str(valor).strip()
        if "," in valor:
            valor = valor.replace(".", "").replace(",", ".")
        try:
            return float(valor)
        except ValueError:
            return 0.0

    def tratar_retorno(self, context):
        if "<RetornoErro>" not in context.resultado:
            return RuleDecision.retornar(context.resultado)

        if not self._erro_politica_ou_meio_pagamento(context.resultado):
            return super().tratar_retorno(context)

        if getattr(context, "pi_detalhes_consulta", None) is not None:
            return super().tratar_retorno(context)

        detalhes = self._detalhes_consulta_divida(context)
        context.pi_detalhes_consulta = detalhes
        self.atualizar_detalhes(context, detalhes)
        return RuleDecision.recalcular()

    def _erro_politica_ou_meio_pagamento(self, resultado: str) -> bool:
        resultado_normalizado = normalizar_nome(resultado)
        return (
            ("MEIO DE PAGAMENTO" in resultado_normalizado and "NAO ENCONTRADO" in resultado_normalizado)
            or ("POLITICA" in resultado_normalizado and "NAO ENCONTRADO" in resultado_normalizado)
            or "CONJUNTO DE POLITICA" in resultado_normalizado
        )
