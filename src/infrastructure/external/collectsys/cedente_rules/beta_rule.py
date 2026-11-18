from src.shared.utils import capturar_intervalo_valor_entrada_cedente_81, capturar_parcelamento_max, capturar_intervalo_parcelamento, extrair_tag
from src.shared.utils.xml_tratamentos import capturar_valor, forcar_detalhe_vazio, gerar_xml_detalhe_calculo
from src.infrastructure.logging.logger_config import setup_logger

from .base import BetaLikeCedenteRule
from .types import RuleDecision


class BetaCedenteRule(BetaLikeCedenteRule):
    log = setup_logger("collectsys_beta_rule", "collectsys_beta_rule.log")
    MENSAGEM_SOMENTE_AVISTA = "Apenas propostas a vista para esse contrato"

    def montar_xml(self, context):
        contexto_produto = self._resolver_contexto_produto(context)
        if contexto_produto in ("reneg", "emprestimo") and self._tem_condicao_parciais(context):
            self.aplicar_condicao_xml_divida(context)

        match contexto_produto:
            case "cartao_35":
                self._montar_xml_cartao_35(context)
            case "reneg":
                self._montar_xml_reneg(context)
            case "emprestimo":
                self._montar_xml_emprestimo(context)
            case _:
                self._montar_xml_cartao_maior_35(context)

    def _resolver_contexto_produto(self, context) -> str:
        produto = (context.produto or context.nm_produto or "").upper()

        if context.cartao_35 == "SIM":
            return "cartao_35"
        if "RENEG" in produto:
            return "reneg"
        if "EP" in produto or "EMPREST" in produto:
            return "emprestimo"
        return "cartao_maior_35"

    def _montar_xml_base(self, context, detalhes=None):
        context.desconto = 200
        detalhes = detalhes or []

        usar_valor_enviado = (
            context.parcelado == "VALOR ENTRADA PD"
            and context.valor_entrada
            and context.valor_entrada > 0
        )
        if "VALOR ENTRADA" in context.parcelado and not context.resultado and not usar_valor_enviado:
            context.valor_entrada = 1

        self.definir_data_vencimento(context)
        self.atualizar_detalhes(
            context,
            detalhes,
            force_empty=forcar_detalhe_vazio(context.id_cedente, detalhes) and context.cartao_35 is None,
        )

    def _montar_xml_cartao_35(self, context):
        self._montar_xml_base(
            context,
            detalhes=[["PARCELAMENTO CARTAO BETA", "S", 2826, "Acordo", "Manual"]],
        )

    def _montar_xml_cartao_maior_35(self, context):
        self._montar_xml_base(context)

    def _montar_xml_reneg(self, context):
        self._montar_xml_base(context, detalhes=self._detalhes_parciais(context))

    def _montar_xml_emprestimo(self, context):
        self._montar_xml_base(context, detalhes=self._detalhes_parciais(context))

    def _tem_condicao_parciais(self, context) -> bool:
        return self._quantidade_parcelas_condicao(getattr(context, "condicao", None)) is not None

    def _detalhes_parciais(self, context):
        if not self._tem_condicao_parciais(context):
            return None
        return [["PARCIAIS BETA", "S", 2825, "Acordo", "Manual"]]

    def tratar_retorno(self, context):
        if "<RetornoErro>" not in context.resultado:
            if "VALOR ENTRADA" in context.parcelado:
                self.log.info(
                    "beta_valor_entrada_sucesso id_cliente=%s plano=%s parcelado=%s cartao_35=%s retorno=%s",
                    context.id_cliente,
                    context.plano,
                    context.parcelado,
                    context.cartao_35,
                    self._montar_retorno_entrada(context),
                )
                return RuleDecision.retornar(self._montar_retorno_entrada(context))
            return RuleDecision.retornar(context.resultado)

        if "VALOR ENTRADA" in context.parcelado:
            valor_minimo_entrada = context.valor_minimo_entrada
            valor_maximo_entrada = context.valor_maximo_entrada
            parcelamento_min = context.parcelamento_min
            parcelamento_max = context.parcelamento_max
            self.log.info(
                "beta_valor_entrada_erro id_cliente=%s plano=%s parcelado=%s cartao_35=%s mensagem=%s valor_min_atual=%s valor_max_atual=%s parcela_min_atual=%s parcela_max_atual=%s",
                context.id_cliente,
                context.plano,
                context.parcelado,
                context.cartao_35,
                context.resultado_tratado,
                valor_minimo_entrada,
                valor_maximo_entrada,
                parcelamento_min,
                parcelamento_max,
            )

            if self._eh_somente_avista(context):
                return self._retornar_somente_avista(context)

            if "VALOR" in context.resultado.upper():
                novo_valor_minimo, novo_valor_maximo = capturar_intervalo_valor_entrada_cedente_81(context.resultado)
                if context.cartao_35 == 'SIM' and not novo_valor_minimo and not novo_valor_maximo:
                    novo_valor_minimo = capturar_valor(context.resultado)
                    novo_valor_maximo = novo_valor_minimo

                if novo_valor_minimo is not None:
                    if novo_valor_maximo is not None and novo_valor_minimo == novo_valor_maximo:
                        valor_minimo_entrada = novo_valor_minimo
                    else:
                        valor_minimo_entrada = novo_valor_minimo + 1
                if novo_valor_maximo is not None:
                    valor_maximo_entrada = novo_valor_maximo

                context.valor_minimo_entrada = valor_minimo_entrada
                context.valor_maximo_entrada = valor_maximo_entrada
                self.log.info(
                    "beta_valor_entrada_capturado id_cliente=%s valor_min=%s valor_max=%s",
                    context.id_cliente,
                    context.valor_minimo_entrada,
                    context.valor_maximo_entrada,
                )

                if context.parcelado == "VALOR ENTRADA PD":
                    return RuleDecision.retornar(
                        self._montar_retorno_entrada(
                            context,
                            valor_minimo_entrada=valor_minimo_entrada,
                            valor_maximo_entrada=valor_maximo_entrada,
                            parcelamento_min=parcelamento_min or 1,
                            parcelamento_max=parcelamento_max or int(context.plano or 1),
                        )
                    )

            if (
                "QUANTIDADE DE PARCELAS" in context.resultado.upper()
                or "PLANO MAXIMO" in context.resultado_normalizado.upper()
                or "PLANO MINIMO" in context.resultado_normalizado.upper()
            ):
                parcelamento_min, parcelamento_max_intervalo = capturar_intervalo_parcelamento(context.resultado)
                parcelamento_max = capturar_parcelamento_max(context.resultado)
                if parcelamento_max_intervalo is not None:
                    parcelamento_max = parcelamento_max_intervalo
                if parcelamento_min is not None:
                    context.parcelamento_min = parcelamento_min
                if parcelamento_max is not None:
                    context.parcelamento_max = parcelamento_max
                self.log.info(
                    "beta_parcelamento_capturado id_cliente=%s parcela_min=%s parcela_max=%s mensagem=%s",
                    context.id_cliente,
                    context.parcelamento_min,
                    context.parcelamento_max,
                    context.resultado_tratado,
                )
            else:
                context.valor_entrada = valor_maximo_entrada
                self.log.info(
                    "beta_recalcular_valor_entrada id_cliente=%s novo_valor_entrada=%s",
                    context.id_cliente,
                    context.valor_entrada,
                )
                return RuleDecision.recalcular()

            if valor_maximo_entrada and valor_minimo_entrada and parcelamento_max:
                self.log.info(
                    "beta_valor_entrada_retorno_final id_cliente=%s valor_min=%s valor_max=%s parcela_min=%s parcela_max=%s cartao_35=%s",
                    context.id_cliente,
                    valor_minimo_entrada,
                    valor_maximo_entrada,
                    parcelamento_min,
                    parcelamento_max,
                    context.cartao_35,
                )
                return RuleDecision.retornar(
                    (
                        valor_minimo_entrada,
                        valor_maximo_entrada,
                        parcelamento_min or 1,
                        parcelamento_max,
                        context.cartao_35,
                    )
                )

            return RuleDecision.retornar(self._montar_retorno_entrada(
                context,
                valor_minimo_entrada=valor_minimo_entrada,
                valor_maximo_entrada=valor_maximo_entrada,
                parcelamento_min=parcelamento_min,
                parcelamento_max=parcelamento_max,
            ))

        elif context.parcelado == "":
            if self._eh_somente_avista(context):
                return RuleDecision.retornar(self.MENSAGEM_SOMENTE_AVISTA)
            return RuleDecision.retornar(context.resultado_tratado)

        if "valor minimo de adesao" in context.resultado_tratado_normalizado:
            return RuleDecision.retornar(context.resultado)

        return None

    def _eh_somente_avista(self, context) -> bool:
        mensagem = context.resultado_tratado_normalizado
        return (
            "para calculo de parciais a vencer/em atraso, necessario marcar as dividas que estao em atraso/a vencer."
            in mensagem
            or "nao existem ofertas de renegociacao (a prazo) para o(s) contrato(s) informado(s)." in mensagem
            or "nao existem opcoes de parcelamento de fatura" in mensagem
            or (
                "existe divida de cartao selecionada com ate 35 dias de atraso" in mensagem
                and "renegociacao nao permitida" in mensagem
            )
        )

    def _retornar_somente_avista(self, context):
        context.mensagem = self.MENSAGEM_SOMENTE_AVISTA
        return RuleDecision.retornar((0, 0, 1, 1, context.cartao_35))

    def _montar_retorno_entrada(
        self,
        context,
        valor_minimo_entrada=None,
        valor_maximo_entrada=None,
        parcelamento_min=None,
        parcelamento_max=None,
    ):
        valor_minimo_entrada = (
            context.valor_minimo_entrada
            if valor_minimo_entrada is None
            else valor_minimo_entrada
        )
        valor_maximo_entrada = (
            context.valor_maximo_entrada
            if valor_maximo_entrada is None
            else valor_maximo_entrada
        )
        parcela_min = parcelamento_min or context.parcelamento_min or 1
        parcela_max = parcelamento_max or int(context.plano or 1)
        valor_parcela = extrair_tag(context.resultado, "<ValorParcela>", "</ValorParcela>")

        if valor_parcela is not None:
            valor_parcela = float(str(valor_parcela).replace(",", "."))

        valor_base = valor_parcela
        if valor_base is None:
            valor_base = valor_maximo_entrada
        if valor_base is None:
            valor_base = valor_minimo_entrada
        if valor_base is None:
            valor_base = context.valor_entrada or 0

        valor_min = valor_minimo_entrada if valor_minimo_entrada is not None else valor_base
        valor_max = valor_maximo_entrada if valor_maximo_entrada is not None else valor_base
        return (valor_min, valor_max, parcela_min, parcela_max, context.cartao_35)
