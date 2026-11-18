import asyncio
from datetime import date, timedelta
import logging
import math
import os

from src.shared.utils.data import capturar_data, validacao_dia_util
from src.shared.utils.xml_tratamentos import capturar_valor, extrair_tag

from .default_rule import DefaultCedenteRule
from .types import RuleDecision, normalize_text


logger = logging.getLogger(__name__)


# Na ZETA o detalhe NMPRODUTOCEDENTE traz apenas o codigo do produto (ex.: "44").
# O mapa abaixo traduz o codigo para o nome do produto usado na negociacao.
ZETA_PRODUTOS = {
    "44": "EMPRESTIMO",
    "12A": "CARTAO",
    "111": "CARTAO",
    "12": "CARTAO",
    "5": "CP_PREVENTIVO",
}


class ZetaCedenteRule(DefaultCedenteRule):
    @staticmethod
    def tratar_produto(codigo: str | None) -> str | None:
        """Traduz o codigo do produto vindo do detalhe para o nome."""
        if not codigo:
            return None
        return ZETA_PRODUTOS.get(str(codigo).strip().upper())

    def definir_data_vencimento(self, context):
        """Aplica previamente a janela maxima aceita pela ZETA.

        Sem essa normalizacao o calculo era enviado com D+6, recebia o limite
        D+4 como erro de negocio e precisava repetir a mesma operacao.
        """
        try:
            dias_limite = max(0, int(os.getenv("ZETA_DIAS_MAX_PAGAMENTO", "4")))
        except (TypeError, ValueError):
            dias_limite = 4

        data_limite = validacao_dia_util(date.today() + timedelta(days=dias_limite))
        data_solicitada = self._normalizar_data(getattr(context, "vencimento", None))
        data_vencimento = (
            data_solicitada
            if data_solicitada and data_solicitada <= data_limite
            else data_limite
        )
        context.vencimento = data_vencimento
        context.data_vencimento = data_vencimento

    def montar_xml(self, context):
        context.desconto = 100
        self.definir_data_vencimento(context)
        # A ZETA exige a estrutura de detalhe no SOAP, mas sem enviar
        # valores de detalhe. Mantem somente as tags, como no fluxo TETA.
        self.atualizar_detalhes(context, [], force_empty=True)

    def tratar_retorno(self, context):
        if "<RetornoErro>" not in context.resultado:
            return RuleDecision.retornar(context.resultado)

        if "data" in context.resultado_normalizado:
            nova_data = capturar_data(context.resultado)
            if nova_data:
                data_atual = self._normalizar_data(
                    getattr(context, "data_vencimento", None)
                )
                if nova_data != data_atual:
                    context.data_vencimento = nova_data
                    return RuleDecision.recalcular()
                logger.warning(
                    "zeta_data_sem_alteracao id_cliente=%s plano=%s data=%s",
                    context.id_cliente,
                    context.plano,
                    nova_data,
                )
                return RuleDecision.retornar(context.resultado)
            logger.warning(
                "zeta_data_sem_match id_cliente=%s plano=%s",
                context.id_cliente,
                context.plano,
            )

        if "valor" in context.resultado_normalizado:
            novo_valor = capturar_valor(context.resultado)
            if novo_valor is not None:
                try:
                    valor_atual = float(getattr(context, "valor_entrada", 0) or 0)
                except (TypeError, ValueError):
                    valor_atual = 0

                # Aumentar a entrada nao corrige uma parcela restante abaixo
                # do minimo. Guarda o valor para os proximos planos, mas nao
                # repete o mesmo plano com um payload que continuara invalido.
                if "valor minimo das parcelas" in context.resultado_normalizado:
                    context.valor_entrada = novo_valor
                    logger.info(
                        "zeta_parcela_minima_detectada id_cliente=%s plano=%s valor=%s",
                        context.id_cliente,
                        context.plano,
                        novo_valor,
                    )
                    return RuleDecision.retornar(context.resultado)

                if abs(float(novo_valor) - valor_atual) > 0.005:
                    context.valor_entrada = novo_valor
                    return RuleDecision.recalcular()
                logger.warning(
                    "zeta_valor_entrada_sem_alteracao id_cliente=%s plano=%s valor=%s",
                    context.id_cliente,
                    context.plano,
                    novo_valor,
                )
                return RuleDecision.retornar(context.resultado)
            logger.warning(
                "zeta_valor_entrada_sem_match id_cliente=%s plano=%s",
                context.id_cliente,
                context.plano,
            )

        # Mantem os fallbacks tecnicos compartilhados. Se nenhum deles alterar
        # o payload, uma consulta parcelada da ZETA nao deve repetir a mesma
        # requisicao externa ate esgotar as tentativas.
        decisao = super().tratar_retorno(context)
        if decisao is not None:
            return decisao
        if context.parcelado:
            return RuleDecision.retornar(context.resultado)
        return None

    def valor_entrada_parcelamento(self, contrato, parcelas: int, valor_padrao: float) -> float:
        valores_por_plano = getattr(contrato, "valores_entrada_zeta", {})
        return float(valores_por_plano.get(parcelas, 0) or 0)

    def resultado_parcelamento_cache(self, contrato, parcelas: int) -> str | None:
        resultados_por_plano = getattr(contrato, "resultados_parcelamento_zeta", {})
        return resultados_por_plano.get(parcelas)

    async def obter_parcelamento_max(
        self,
        contrato,
        executar_calculo,
        limite_max_parcelas: int = 36,
    ) -> None:
        menor_plano = 1
        maior_plano = min(
            limite_max_parcelas,
            max(1, int(contrato.parcelamento_max or limite_max_parcelas)),
        )
        maior_valido = 0
        planos_testados = []
        valor_entrada_busca = float(contrato.valor or 0)
        valores_por_plano = dict(getattr(contrato, "valores_entrada_zeta", {}))
        resultados_por_plano = dict(
            getattr(contrato, "resultados_parcelamento_zeta", {})
        )
        status_por_plano: dict[int, bool] = {}
        ultimo_resultado_por_plano: dict[int, str] = {}

        def registrar_resultado(
            plano: int,
            resultado: str,
            calculo,
            atualizar_valor_busca: bool,
        ) -> bool:
            nonlocal valor_entrada_busca

            data_corrigida = self._normalizar_data(getattr(calculo, "data_vencimento", None))
            if data_corrigida:
                contrato.atualizar_data(data_corrigida)

            try:
                valor_corrigido = float(getattr(calculo, "valor_entrada", 0) or 0)
            except (TypeError, ValueError):
                valor_corrigido = 0

            if atualizar_valor_busca and valor_corrigido > 0:
                valor_entrada_busca = valor_corrigido
            valores_por_plano[plano] = valor_corrigido
            contrato.valores_entrada_zeta = valores_por_plano
            resultado_valido = self._resultado_tem_parcela(resultado)
            status_por_plano[plano] = resultado_valido
            ultimo_resultado_por_plano[plano] = resultado
            if resultado_valido:
                resultados_por_plano[plano] = resultado
                contrato.resultados_parcelamento_zeta = resultados_por_plano
            return resultado_valido

        async def testar_plano(plano: int) -> bool:
            if plano in status_por_plano:
                return status_por_plano[plano]

            planos_testados.append(plano)
            resultado, calculo = await executar_calculo(plano, valor_entrada_busca)
            return registrar_resultado(plano, resultado, calculo, True)

        async def pre_carregar_plano(plano: int) -> bool:
            if plano in status_por_plano:
                return status_por_plano[plano]

            planos_testados.append(plano)
            resultado, calculo = await executar_calculo(plano, 0)
            return registrar_resultado(plano, resultado, calculo, False)

        # A ZETA normalmente disponibiliza o teto. Testa-lo primeiro evita
        # calcular o plano intermediario e depois repetir o calculo no teto.
        # O plano 1 sempre faz parte do retorno final e e antecipado em
        # paralelo; quando valido, o cache evita repeti-lo depois.
        planos_pre_carregamento = [
            plano
            for plano in (1,)
            if plano <= maior_plano and plano != maior_plano
        ]
        resultados_iniciais = await asyncio.gather(
            testar_plano(maior_plano),
            *(pre_carregar_plano(plano) for plano in planos_pre_carregamento),
        )
        teto_valido = resultados_iniciais[0]
        planos_validos_pre_carregados = [
            plano
            for plano, valido in zip(
                planos_pre_carregamento,
                resultados_iniciais[1:],
            )
            if valido
        ]
        if planos_validos_pre_carregados:
            maior_valido = max(planos_validos_pre_carregados)

        # Quando a ZETA informa a parcela minima, usa o valor a vista ja
        # calculado para testar diretamente a faixa provavel. A busca binaria
        # abaixo continua sendo o fallback se a fronteira nao for confirmada.
        busca_direta_concluida = False
        if teto_valido:
            maior_valido = maior_plano
            menor_plano = maior_plano + 1
        else:
            resultado_teto = ultimo_resultado_por_plano.get(maior_plano, "")
            resultado_avista = resultados_por_plano.get(1, "")
            valor_minimo_parcela = self._valor_minimo_parcela(resultado_teto)
            valor_avista = self._valor_primeira_parcela(resultado_avista)

            if valor_minimo_parcela and valor_avista:
                plano_estimado = max(
                    1,
                    min(
                        maior_plano - 1,
                        math.ceil(valor_avista / valor_minimo_parcela),
                    ),
                )
                planos_faixa = sorted({
                    plano
                    for plano in (
                        plano_estimado - 1,
                        plano_estimado,
                        plano_estimado + 1,
                    )
                    if 1 <= plano < maior_plano
                })
                planos_exibicao_estimados = sorted({
                    plano
                    for plano in (
                        int(plano_estimado / 2),
                        int(plano_estimado / 4),
                    )
                    if plano >= 1
                })
                await asyncio.gather(
                    *(testar_plano(plano) for plano in planos_faixa),
                    *(
                        pre_carregar_plano(plano)
                        for plano in planos_exibicao_estimados
                        if plano not in planos_faixa
                    ),
                )

                for plano in reversed(planos_faixa):
                    if (
                        status_por_plano.get(plano) is True
                        and status_por_plano.get(plano + 1) is False
                    ):
                        maior_valido = plano
                        busca_direta_concluida = True
                        break

                logger.info(
                    "zeta_parcelamento_estimado id_cliente=%s id_contrato=%s valor_avista=%s valor_minimo_parcela=%s plano_estimado=%s planos=%s plano_confirmado=%s",
                    contrato.id_cliente,
                    contrato.id_contrato,
                    valor_avista,
                    valor_minimo_parcela,
                    plano_estimado,
                    planos_faixa,
                    maior_valido if busca_direta_concluida else None,
                )

            maior_plano -= 1

        while not busca_direta_concluida and menor_plano <= maior_plano:
            plano = (menor_plano + maior_plano) // 2
            if await testar_plano(plano):
                maior_valido = plano
                menor_plano = plano + 1
            else:
                maior_plano = plano - 1

        contrato.parcelamento_max = max(1, maior_valido)
        logger.info(
            "zeta_parcelamento_max_busca id_cliente=%s id_contrato=%s planos=%s parcela_max=%s data_pagamento=%s",
            contrato.id_cliente,
            contrato.id_contrato,
            planos_testados,
            contrato.parcelamento_max,
            contrato.data_pagamento,
        )

    @staticmethod
    def _normalizar_data(valor):
        if isinstance(valor, date):
            return valor
        if isinstance(valor, str):
            try:
                return date.fromisoformat(valor.split("T", 1)[0])
            except ValueError:
                return None
        return None

    @staticmethod
    def _resultado_tem_parcela(resultado: str) -> bool:
        return "<RetornoErro>" not in resultado and "<ParcelaAcordo>" in resultado

    @staticmethod
    def _valor_minimo_parcela(resultado: str) -> float | None:
        if "valor minimo das parcelas" not in normalize_text(resultado):
            return None
        return capturar_valor(resultado)

    @staticmethod
    def _valor_primeira_parcela(resultado: str) -> float | None:
        valor = extrair_tag(resultado, "<ValorParcela>")
        if not valor:
            return None
        try:
            return float(valor.replace(",", "."))
        except (TypeError, ValueError):
            return None
