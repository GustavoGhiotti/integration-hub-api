import re

from src.domain.exceptions.collectsys_exception import CollectSysException
from src.infrastructure.external.collectsys.consulta_contrato_detalhe import ConsultaContratoDetalhe

from .default_rule import DefaultCedenteRule
from .types import RuleDecision
from src.shared.utils import (
    capturar_intervalo_parcelamento,
    capturar_parcelamento_max,
    extrair_tag,
)


class TetaSpecialCedenteRule(DefaultCedenteRule):
    PRODUTO_INFORMATIVO = "ILPURA"

    @staticmethod
    def _normalizar_produto(produto) -> str:
        return re.sub(r"[^A-Z0-9]", "", str(produto or "").upper())

    @staticmethod
    def _valor_decimal_brasileiro(valor) -> float | None:
        texto = str(valor or "").strip().replace("R$", "").replace(" ", "")
        if not texto:
            return None
        try:
            if "," in texto:
                texto = texto.replace(".", "").replace(",", ".")
            return round(float(texto), 2)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _mensagem_debito_automatico(valor: float) -> str:
        valor_formatado = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return (
            f"O cliente deve manter em conta o valor de R$ {valor_formatado}, que será "
            "debitado automaticamente para quitação da dívida."
        )

    def consultar_contexto_produto(self, id_cliente: int, id_contrato: int):
        detalhes = ConsultaContratoDetalhe(id_cliente, id_contrato).consultar_detalhes_teta()
        produto = detalhes.get("produto")
        contexto = {"produto": produto, "informativo": False}
        if self._normalizar_produto(produto) != self.PRODUTO_INFORMATIVO:
            return contexto

        valor = self._valor_decimal_brasileiro(detalhes.get("valorCurvaAtraso"))
        if valor is None or valor <= 0:
            raise CollectSysException(
                mensagem="VALOR_CURVA_ATRASO nao encontrado para o produto ILPURA."
            )
        contexto.update(
            informativo=True,
            valor=valor,
            mensagem=self._mensagem_debito_automatico(valor),
        )
        return contexto

    def aplicar_produto_informativo_verifica(
        self, item: dict, contexto: dict, parcelas: list[dict], total_parcelas: int
    ) -> dict:
        valor = contexto["valor"]
        item["valorOriginal"] = {
            "valor": valor,
            "parcelasEmAtraso": parcelas,
            "quantidadeParcelasEmAtraso": len(parcelas),
            "quantidadeParcelas": total_parcelas or len(parcelas),
        }
        item["propostaSemDesconto"] = {"valor": valor}
        item["propostaAvista"] = {
            "valor": valor,
            "mensagem": contexto["mensagem"],
        }
        return item

    def montar_produto_informativo_parcelado(
        self, contexto: dict, nome_cedente: str, id_cliente: int, id_contrato: int
    ) -> dict:
        return {
            "origem": "COLLECTSYS",
            "nomeCedente": nome_cedente,
            "idCliente": id_cliente,
            "contrato": id_contrato,
            "produto": contexto["produto"],
            "propostas": [
                {
                    "valorEntrada": contexto["valor"],
                    "mensagem": contexto["mensagem"],
                }
            ],
        }

    def montar_produto_informativo_proposta(
        self, contexto: dict, id_contrato: int
    ) -> dict:
        return {
            "origem": "COLLECTSYS",
            "valorEntrada": contexto["valor"],
            "mensagem": contexto["mensagem"],
            "contrato": id_contrato,
            "produto": contexto["produto"],
        }

    def montar_xml(self, context):
        context.desconto = 200

        self.definir_data_vencimento(context)
        self.atualizar_detalhes(context, [], force_empty=True)

    def tratar_retorno(self, context):
        if "VALOR ENTRADA" in context.parcelado:
            if "<RetornoErro>" not in context.resultado:
                return RuleDecision.retornar(self._montar_retorno_parcelamento(context))

            parcelamento_min, parcelamento_max_intervalo = capturar_intervalo_parcelamento(context.resultado)
            parcelamento_max = capturar_parcelamento_max(context.resultado)
            if parcelamento_max_intervalo is not None:
                parcelamento_max = parcelamento_max_intervalo
            if parcelamento_min is not None:
                context.parcelamento_min = parcelamento_min
            if parcelamento_max is not None:
                context.parcelamento_max = parcelamento_max
            return RuleDecision.retornar(self._montar_retorno_parcelamento(context))

        return super().tratar_retorno(context)

    def _montar_retorno_parcelamento(self, context):
        valor_parcela = extrair_tag(context.resultado, "<ValorParcela>", "</ValorParcela>")
        if valor_parcela is not None:
            valor_parcela = float(str(valor_parcela).replace(",", "."))

        valor_base = valor_parcela if valor_parcela is not None else context.valor_entrada or 0
        parcela_min = context.parcelamento_min or 1
        parcela_max = context.parcelamento_max or int(context.plano or 1)
        return (valor_base, valor_base, parcela_min, parcela_max, context.cartao_35)
