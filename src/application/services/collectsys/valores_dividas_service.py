from src.domain.entities.cedentes import CEDENTES_TETA_COMUM, CEDENTES_CALCULO_DETALHE, CEDENTES_PARCELAMENTO_MIN_MAX, BancoBeta
from src.domain.exceptions.collectsys_exception import *
from src.domain.entities import Acordo, Divida
from src.infrastructure.external.collectsys import Calcular, EmitirBoleto
from src.infrastructure.external.collectsys.cedente_rules import get_cedente_rule
from src.application.services.collectsys.meios_pagamentos_service import Boleto
from src.shared.utils import capturar_intervalo_parcelamento, extrair_tag, extrair_array, mensagem_retorno_calculo
from src.shared.utils.data import proximo_dia_util
from typing import List, Union
from concurrent.futures import ThreadPoolExecutor
import os
import asyncio
import contextvars
from copy import deepcopy
import re
from datetime import date, timedelta
from src.infrastructure.logging.logger_config import setup_logger

_COLLECTSYS_CALC_WORKERS = 20
_CALC_EXECUTOR = ThreadPoolExecutor(max_workers=_COLLECTSYS_CALC_WORKERS)

def _run_calc(func):
    loop = asyncio.get_running_loop()
    ctx = contextvars.copy_context()
    return loop.run_in_executor(_CALC_EXECUTOR, ctx.run, func)


def _capturar_intervalo_de_erros(resultados_por_parcela: dict[int, str]) -> tuple[int | None, int | None]:
    parcela_min = None
    parcela_max = None

    for resultado in resultados_por_parcela.values():
        if "<RetornoErro>" not in resultado:
            continue

        min_erro, max_erro = capturar_intervalo_parcelamento(resultado)
        if min_erro is not None:
            parcela_min = max(parcela_min or min_erro, min_erro)
        if max_erro is not None:
            parcela_max = min(parcela_max or max_erro, max_erro)

    return parcela_min, parcela_max


def _resultado_tem_parcela(resultado: str) -> bool:
    return "<RetornoErro>" not in resultado and "<ParcelaAcordo>" in resultado


def _resultado_xml_sem_parcelas(resultado: str) -> bool:
    return "<RetornoErro>" not in resultado and "<Acordo>" in resultado and "<ParcelaAcordo>" not in resultado


def _limitar_contratos_parcelados(contratos: List[Divida], limite: int = 4) -> List[Divida]:
    if len(contratos) <= limite:
        return contratos

    contratos_ordenados = sorted(contratos, key=lambda contrato: contrato.qtd_parcelas)
    if limite <= 1:
        return [contratos_ordenados[-1]]

    contratos_por_parcela = {contrato.qtd_parcelas: contrato for contrato in contratos_ordenados}
    parcelas = sorted(contratos_por_parcela)
    selecionadas = {parcelas[0], parcelas[-1]}

    while len(selecionadas) < limite:
        selecionadas_ordenadas = sorted(selecionadas)
        melhor_parcela = None
        melhor_distancia = -1

        for parcela in parcelas:
            if parcela in selecionadas:
                continue
            distancia = min(abs(parcela - escolhida) for escolhida in selecionadas_ordenadas)
            if distancia > melhor_distancia or (
                distancia == melhor_distancia and (melhor_parcela is None or parcela > melhor_parcela)
            ):
                melhor_distancia = distancia
                melhor_parcela = parcela

        if melhor_parcela is None:
            break
        selecionadas.add(melhor_parcela)

    return [contratos_por_parcela[parcela] for parcela in sorted(selecionadas)]


class ValoresDividas:
    log = setup_logger("collectsys_parcelado_debug", "collectsys_parcelado_debug.log")

    @staticmethod
    def proposta_avista_cartao_35(contrato: Divida, incluir_boleto: bool = True) -> dict | None:
        boleto = None
        if incluir_boleto:
            boleto = Boleto.obter_original_por_divida_parcelado(
                contrato.id_cliente,
                contrato.id_contrato,
                contrato.id_cedente,
                contrato.xml,
            )

        resultado = EmitirBoleto(
            servidor="Cobranca",
            id_cliente=contrato.id_cliente,
            id_acordo=0,
            parcela=1,
            id_cedente=contrato.id_cedente,
        ).emitir_original(contrato.xml)

        valor_documento = extrair_tag(resultado, "<VALOR_DOCUMENTO>", "</VALOR_DOCUMENTO>")
        if not valor_documento:
            ValoresDividas.log.info(
                "beta_avista_original_sem_valor id_cliente=%s id_contrato=%s retorno=%s",
                contrato.id_cliente,
                contrato.id_contrato,
                resultado,
            )
            return None

        valor = float(valor_documento.replace(".", "").replace(",", "."))
        data_pagamento = proximo_dia_util(date.today() + timedelta(days=1))
        proposta = {
            "valorEntrada": valor,
            "dataPagamento": data_pagamento,
        }
        if incluir_boleto:
            proposta["boleto"] = boleto
        return proposta

    async def calcular_valores(contratos: List[Union[Acordo, Divida]], data) -> list:
            calculos_dividas = []

            for contrato in contratos:

                if isinstance(contrato, Acordo):
                    continue

                #Valor sem desconto
                tarefa_sem_desc = _run_calc(lambda c=contrato: Calcular(
                                                            c.nome_cedente,
                                                            c.id_cliente,
                                                            c.id_cedente,
                                                            c.qtd_parcelas,
                                                            c.valor,
                                                            c.xml
                                                            ).calcular_divida())

                calculos_dividas.append({
                                        "tarefa": tarefa_sem_desc,
                                        "idContrato": contrato.id_contrato,
                                        "tipo": "semDesconto"
                                    })

                # Valor com desconto
                skip_desconto = getattr(contrato, "skip_desconto", False)
                if not skip_desconto and contrato.id_cedente != 1:
                    if contrato.id_cedente not in CEDENTES_CALCULO_DETALHE:
                        tarefa_desc = _run_calc(lambda c=contrato: Calcular(
                                                                c.nome_cedente,
                                                                c.id_cliente,
                                                                c.id_cedente,
                                                                c.qtd_parcelas,
                                                                c.valor,
                                                                c.xml,
                                                                data
                                                                ).calcular_acordo())
                    else:
                        tarefa_desc = _run_calc(lambda c=contrato: Calcular(
                                                                c.nome_cedente,
                                                                c.id_cliente,
                                                                c.id_cedente,
                                                                c.qtd_parcelas,
                                                                c.valor,
                                                                c.xml,
                                                                data
                                                            ).calcular_acordo_com_detalhes())

                    calculos_dividas.append({
                                        "tarefa": tarefa_desc,
                                        "idContrato": contrato.id_contrato,
                                        "tipo": "comDesconto"
                                    })

            #Pegando apenas a função de calculo das dividas e colocando em tarefas
            tarefas = [item["tarefa"] for item in calculos_dividas]

            resultado_raw = await asyncio.gather(*tarefas, return_exceptions=True)

            resultados = [
                            {
                                "resultado": (
                                    f"<RetornoErro><Mensagem>{resultado}</Mensagem></RetornoErro>"
                                    if isinstance(resultado, Exception)
                                    else resultado
                                ),
                                "idContrato": calculos_dividas[i]["idContrato"],
                                "tipo": calculos_dividas[i]["tipo"]
                            } for i, resultado in enumerate(resultado_raw)
                        ]

            return resultados

    async def obter_parcelamento_max(contrato: Divida) -> None:
        rule = get_cedente_rule(contrato.id_cedente)
        limite_max_parcelas = rule.limite_parcelas_divida(contrato.xml) or 36
        if contrato.id_cedente in (65,73):
            contrato.parcelamento_max = 30
            return

        obter_maximo_customizado = getattr(rule, "obter_parcelamento_max", None)
        if callable(obter_maximo_customizado):
            async def executar_calculo(plano: int, valor_entrada: float):
                calculo = Calcular(
                    contrato.nome_cedente,
                    contrato.id_cliente,
                    contrato.id_cedente,
                    plano,
                    valor_entrada,
                    contrato.xml,
                    contrato.data_pagamento,
                )
                resultado = await _run_calc(
                    lambda c=calculo: c.calcular_acordo_com_detalhes(parcelado="True")
                )
                return resultado, calculo

            await obter_maximo_customizado(
                contrato,
                executar_calculo,
                limite_max_parcelas,
            )
            return

        if contrato.id_cedente == 3:

            xml_parc = Calcular(contrato.nome_cedente, contrato.id_cliente,contrato.id_cedente,
                                        contrato.qtd_parcelas,contrato.valor,contrato.xml).obter_parcelamento_max()

            parcelamento_max = int(extrair_tag(xml_parc, "<PlanoMaximo>","</PlanoMaximo>"))

            contrato.parcelamento_max = min(parcelamento_max, limite_max_parcelas)

        else:

            async def testar_valor(qtd):
                calculo = Calcular(
                    contrato.nome_cedente,
                    contrato.id_cliente,
                    contrato.id_cedente,
                    qtd,
                    contrato.valor,
                    contrato.xml,
                    contrato.data_pagamento
                )

                if contrato.id_cedente not in CEDENTES_CALCULO_DETALHE:
                    resposta = await _run_calc(
                       lambda: calculo.calcular_acordo("True")
                    )
                else:
                    resposta = await _run_calc(
                       lambda: calculo.calcular_acordo_com_detalhes(parcelado="True")
                    )

                return qtd, calculo.plano, resposta

            #Testes iniciais
            faixa_inicial = sorted(
                {min(qtd, limite_max_parcelas) for qtd in (10, 20, 30)}
            )
            max_valido = 0
            maior_testado = 30

            while True:
                tarefas = [asyncio.create_task(testar_valor(q)) for q in faixa_inicial]
                resultados = await asyncio.gather(*tarefas)

                sucesso = []
                for qtd_solicitado, qtd_real, resposta in resultados:
                    if contrato.id_cedente == 51:
                        if "<RetornoErro>" in resposta:
                            erro = extrair_tag(resposta, "<RetornoErro>", "</RetornoErro>") or ""
                            if "service unavailable" in erro.lower():
                                erro =  "No momento cliente possui somente proposta a vista"
                                raise ErroFormalizarAcordo(mensagem=erro)
                    elif "<RetornoErro>" not in resposta:
                        # Banco Beta informa o limite real dentro da propria tratativa.
                        # Quando isso acontecer, usamos esse valor e evitamos novas varreduras.
                        if contrato.id_cedente in CEDENTES_PARCELAMENTO_MIN_MAX and qtd_real < qtd_solicitado:
                            contrato.parcelamento_max = min(limite_max_parcelas, max(1, qtd_real))
                            return
                        sucesso.append(qtd_real)

                if not sucesso:
                    # Nenhum valor da faixa funcionou — precisamos voltar e refinar
                    maior_testado = max(faixa_inicial)
                    break

                max_valido = max(sucesso)
                maior_testado = max(faixa_inicial)

                if contrato.id_cedente in (73, 65) and max_valido >= limite_max_parcelas:
                    break

                if maior_testado >= limite_max_parcelas:
                    break

                if all(q in sucesso for q in faixa_inicial):
                    # Todos os valores da faixa deram certo — testamos a próxima faixa maior
                    proximo = [maior_testado + 10, maior_testado + 20, maior_testado + 30]
                    faixa_inicial = [q for q in proximo if q <= limite_max_parcelas]
                    if not faixa_inicial:
                        break
                else:
                    # Teve erro em algum valor — hora de refinar com varredura paralela
                    break

            # Agora validamos em paralelo o restante do intervalo para achar o maior válido rapidamente
            inicio = max_valido
            fim = min(maior_testado, limite_max_parcelas)
            candidatos = list(range(inicio + 1, fim + 1))
            if candidatos:
                tarefas = [asyncio.create_task(testar_valor(q)) for q in candidatos]
                resultados = await asyncio.gather(*tarefas)
                sucesso = []
                for qtd_solicitado, qtd_real, resposta in resultados:
                    if "<RetornoErro>" in resposta:
                        continue
                    if contrato.id_cedente in CEDENTES_PARCELAMENTO_MIN_MAX and qtd_real < qtd_solicitado:
                        contrato.parcelamento_max = min(limite_max_parcelas, max(1, qtd_real))
                        return
                    sucesso.append(qtd_real)
                if sucesso:
                    max_valido = max(sucesso)
            contrato.parcelamento_max = min(limite_max_parcelas, max(1, max_valido))

    async def valores_parcelados(
        contrato: Divida,
        valor_min=None,
        valor_max=None,
        cartao_35=None,
        parcelamento_min=None,
    ) -> List[Divida]:
        rule = get_cedente_rule(contrato.id_cedente)

        def criar_tarefa(parcelas: int, metodo: str):
            resultado_cache = rule.resultado_parcelamento_cache(contrato, parcelas)
            if resultado_cache is not None:
                async def retornar_resultado_cache():
                    return resultado_cache

                return retornar_resultado_cache()

            valor_entrada = contrato.valor
            if contrato.id_cedente in (81, 104):
                valor_entrada = BancoBeta.valor_entrada(contrato.xml, parcelas, valor_min, valor_max)
            else:
                valor_entrada = rule.valor_entrada_parcelamento(
                    contrato,
                    parcelas,
                    valor_entrada,
                )

            calculo = Calcular(
                contrato.nome_cedente,
                contrato.id_cliente,
                contrato.id_cedente,
                parcelas,
                valor_entrada,
                contrato.xml,
                contrato.data_pagamento
            )
            metodo_calculo = getattr(calculo, metodo)
            if metodo == "calcular_acordo_com_detalhes":
                return _run_calc(lambda: metodo_calculo(parcelado="True", cartao_35=cartao_35))
            return _run_calc(lambda: metodo_calculo("True"))

        # Decide o método de cálculo conforme o cedente
        metodo = "calcular_acordo_com_detalhes" if contrato.id_cedente in CEDENTES_CALCULO_DETALHE else "calcular_acordo"
        eh_cartao_35 = contrato.id_cedente in (81, 104) and cartao_35 == "SIM"

        tarefa_avista = None
        if eh_cartao_35:
            contrato_avista = deepcopy(contrato)
            contrato_avista.qtd_parcelas = 1
            tarefa_avista = _run_calc(
                lambda c=contrato_avista: ValoresDividas.proposta_avista_cartao_35(c)
            )

            if valor_min is None or valor_max is None or parcelamento_min is None:
                calculo_parcelamento = Calcular(
                    contrato.nome_cedente,
                    contrato.id_cliente,
                    contrato.id_cedente,
                    min(contrato.parcelamento_max, 36),
                    contrato.valor,
                    contrato.xml,
                    contrato.data_pagamento,
                )
                retorno_parcelamento = await _run_calc(
                    lambda: calculo_parcelamento.calcular_acordo_com_detalhes(
                        parcelado="VALOR ENTRADA",
                        cartao_35=cartao_35,
                    )
                )
                ValoresDividas.log.info(
                    "beta_retorno_parcelamento_integrado id_cliente=%s id_contrato=%s cartao_35=%s retorno=%s",
                    contrato.id_cliente,
                    contrato.id_contrato,
                    cartao_35,
                    retorno_parcelamento,
                )
                if not isinstance(retorno_parcelamento, tuple) or len(retorno_parcelamento) != 5:
                    raise CollectSysException(mensagem=str(retorno_parcelamento))

                valor_min, valor_max, parcelamento_min, parcela_max, cartao_35 = retorno_parcelamento
                contrato.parcelamento_max = parcela_max
                if valor_max:
                    contrato.valor = valor_max

        # --- Coletar todas as quantidades de parcelas possíveis (sem duplicar) ---
        qtds_parcelas = set()

        # Sempre incluir 1
        qtds_parcelas.add(1)
        if parcelamento_min and parcelamento_min >= 1:
            qtds_parcelas.add(parcelamento_min)

        # Parcelamento máximo do contrato
        if contrato.parcelamento_max >= 1:
            qtds_parcelas.add(contrato.parcelamento_max)

        # Testa divisões do contrato sem alterar o objeto original
        backup_parcelas = contrato.qtd_parcelas

        contrato.parcelamento_div2()
        if contrato.qtd_parcelas >= 1:
            qtds_parcelas.add(contrato.qtd_parcelas)

        contrato.parcelamento_div4()
        if contrato.qtd_parcelas >= 1:
            qtds_parcelas.add(contrato.qtd_parcelas)

        # Restaura o valor original
        contrato.qtd_parcelas = backup_parcelas

        # --- Cria tarefas Ãºnicas ordenadas (por nÃºmero de parcelas crescente) ---
        if contrato.id_cedente in (81, 104) and cartao_35 == "SIM":
            qtds_parcelas = {1}
            for parcela_cartao in (1, 4, 5):
                if contrato.parcelamento_max <= 0 or parcela_cartao <= contrato.parcelamento_max:
                    qtds_parcelas.add(parcela_cartao)
            if (
                contrato.parcelamento_max > 1
                and contrato.parcelamento_max not in (4, 5)
            ):
                qtds_parcelas.add(contrato.parcelamento_max)
        elif contrato.id_cedente in CEDENTES_PARCELAMENTO_MIN_MAX and parcelamento_min and parcelamento_min > 1:
            qtds_parcelas = {parcelas for parcelas in qtds_parcelas if parcelas >= parcelamento_min}

        qtds_parcelas = rule.quantidades_parcelamento(
            qtds_parcelas,
            contrato.parcelamento_max,
            contrato,
        )

        qtds_ordenadas = sorted(qtds_parcelas)
        ValoresDividas.log.info(
            "parcelado_tentativas id_cliente=%s id_contrato=%s id_cedente=%s cartao_35=%s valor_min=%s valor_max=%s parcela_min=%s parcela_max=%s parcelas=%s",
            contrato.id_cliente,
            contrato.id_contrato,
            contrato.id_cedente,
            cartao_35,
            valor_min,
            valor_max,
            parcelamento_min,
            contrato.parcelamento_max,
            qtds_ordenadas,
        )

        qtds_calculo = [
            parcela
            for parcela in qtds_ordenadas
            if not (eh_cartao_35 and parcela == 1)
        ]
        tarefas = [criar_tarefa(p, metodo) for p in qtds_calculo]

        if eh_cartao_35 and 1 in qtds_ordenadas and tarefa_avista is None:
            contrato_avista = deepcopy(contrato)
            contrato_avista.qtd_parcelas = 1
            tarefa_avista = _run_calc(
                lambda c=contrato_avista: ValoresDividas.proposta_avista_cartao_35(c)
            )

        resultados = await asyncio.gather(*tarefas)
        resultados_por_parcela = dict(zip(qtds_calculo, resultados))

        if contrato.id_cedente in CEDENTES_TETA_COMUM:
            resultado_avista = resultados_por_parcela.get(1, "")
            avista_disponivel = bool(resultado_avista) and _resultado_tem_parcela(resultado_avista)

            if not avista_disponivel:
                parcela_min_erro, parcela_max_erro = _capturar_intervalo_de_erros(resultados_por_parcela)
                menor_parcelamento = parcelamento_min if parcelamento_min and parcelamento_min > 1 else None

                if parcela_min_erro and parcela_min_erro > 1:
                    menor_parcelamento = parcela_min_erro

                menor_parcelamento = menor_parcelamento or 2

                if parcela_max_erro and parcela_max_erro >= menor_parcelamento:
                    contrato.parcelamento_max = parcela_max_erro
                elif contrato.parcelamento_max < menor_parcelamento:
                    contrato.parcelamento_max = menor_parcelamento

                if menor_parcelamento not in resultados_por_parcela:
                    ValoresDividas.log.info(
                        "parcelado_teta_sem_avista_tenta_minimo id_cliente=%s id_contrato=%s parcela_min=%s parcela_max=%s",
                        contrato.id_cliente,
                        contrato.id_contrato,
                        menor_parcelamento,
                        contrato.parcelamento_max,
                    )
                    resultados_por_parcela[menor_parcelamento] = await criar_tarefa(menor_parcelamento, metodo)

                qtds_ordenadas = sorted(set(qtds_ordenadas).union({menor_parcelamento}))
                qtds_calculo = [
                    parcela
                    for parcela in qtds_ordenadas
                    if not (eh_cartao_35 and parcela == 1)
                ]

        if eh_cartao_35:
            parcela_min_erro, parcela_max_erro = _capturar_intervalo_de_erros(resultados_por_parcela)
            parcelas_retry = set()

            if parcela_min_erro and parcela_min_erro >= 1:
                parcelamento_min = parcela_min_erro
                parcelas_retry.add(parcela_min_erro)

            if parcela_max_erro and parcela_max_erro >= 1:
                contrato.parcelamento_max = parcela_max_erro
                parcelas_retry.add(parcela_max_erro)

            parcelas_retry = {
                parcela
                for parcela in parcelas_retry
                if parcela != 1 and parcela not in resultados_por_parcela
            }
            if parcelas_retry:
                ValoresDividas.log.info(
                    "parcelado_retry_intervalo id_cliente=%s id_contrato=%s parcela_min=%s parcela_max=%s parcelas=%s",
                    contrato.id_cliente,
                    contrato.id_contrato,
                    parcelamento_min,
                    contrato.parcelamento_max,
                    sorted(parcelas_retry),
                )
                novos_resultados = await asyncio.gather(
                    *[criar_tarefa(parcela, metodo) for parcela in sorted(parcelas_retry)]
                )
                resultados_por_parcela.update(dict(zip(sorted(parcelas_retry), novos_resultados)))
                qtds_ordenadas = sorted(set(qtds_ordenadas).union(parcelas_retry))
                qtds_calculo = [
                    parcela
                    for parcela in qtds_ordenadas
                    if not (eh_cartao_35 and parcela == 1)
                ]

        if contrato.id_cedente in CEDENTES_TETA_COMUM:
            parcelas_xml_invalidas = [
                parcela
                for parcela, resultado in resultados_por_parcela.items()
                if _resultado_xml_sem_parcelas(resultado)
            ]
            parcelas_validas = [
                parcela
                for parcela, resultado in resultados_por_parcela.items()
                if _resultado_tem_parcela(resultado)
            ]

            if parcelas_xml_invalidas and parcelas_validas:
                maior_valida = max(parcelas_validas)
                parcelas_acima = [
                    parcela
                    for parcela in resultados_por_parcela
                    if parcela > maior_valida
                ]
                limite_busca = max(parcelas_acima) if parcelas_acima else maior_valida
                parcelas_descobertas = []

                for parcela in range(maior_valida + 1, limite_busca + 1):
                    resultado = resultados_por_parcela.get(parcela)
                    if resultado is None:
                        resultado = await criar_tarefa(parcela, metodo)
                        resultados_por_parcela[parcela] = resultado

                    if not _resultado_tem_parcela(resultado):
                        break

                    parcelas_descobertas.append(parcela)

                if parcelas_descobertas:
                    qtds_ordenadas = sorted(set(qtds_ordenadas).union(parcelas_descobertas))
                    qtds_calculo = [
                        parcela
                        for parcela in qtds_ordenadas
                        if not (eh_cartao_35 and parcela == 1)
                    ]
                    ValoresDividas.log.info(
                        "parcelado_teta_busca_incremental id_cliente=%s id_contrato=%s maior_inicial=%s limite=%s parcelas=%s",
                        contrato.id_cliente,
                        contrato.id_contrato,
                        maior_valida,
                        limite_busca,
                        parcelas_descobertas,
                    )

        proposta_avista = await tarefa_avista if tarefa_avista else None

        contratos: List[Divida] = []
        mensagens_descartadas = []

        # Usa uma data base unica para todas as propostas (preferir plano > 1)
        data_base = ""
        for qtd_parcelas in qtds_calculo:
            resultado = resultados_por_parcela[qtd_parcelas]
            data_parcela = re.sub(r'T.*', '', extrair_tag(resultado, "<DataParcela>", "</DataParcela>") or "")
            if data_parcela and qtd_parcelas > 1:
                data_base = data_parcela
                break
            if data_parcela and not data_base:
                data_base = data_parcela

        for qtd_parcelas in qtds_ordenadas:
            contrato_copia: Divida = deepcopy(contrato)
            contrato_copia.qtd_parcelas = qtd_parcelas

            if eh_cartao_35 and qtd_parcelas == 1:
                if not proposta_avista:
                    ValoresDividas.log.info(
                        "beta_avista_descartada id_cliente=%s id_contrato=%s qtd_parcelas=%s",
                        contrato.id_cliente,
                        contrato.id_contrato,
                        qtd_parcelas,
                    )
                    continue

                valor_avista = proposta_avista["valorEntrada"]
                data_avista = proposta_avista["dataPagamento"]
                contrato_copia.atualizar_valores(
                    valor_avista,
                    0.0,
                    contrato.parcelamento_max,
                    1,
                )
                contrato_copia.boleto = proposta_avista["boleto"]
                contrato_copia.atualizar_data(data_avista)
                contratos.append(contrato_copia)
                continue

            resultado = resultados_por_parcela.get(qtd_parcelas, "")
            if "<RetornoErro>" in resultado or "<ParcelaAcordo>" not in resultado:
                mensagem_descarte = mensagem_retorno_calculo(resultado)
                if mensagem_descarte and mensagem_descarte not in mensagens_descartadas:
                    mensagens_descartadas.append(mensagem_descarte)
                ValoresDividas.log.info(
                    "parcelado_descartado id_cliente=%s id_contrato=%s qtd_parcelas=%s possui_retorno_erro=%s possui_parcela=%s mensagem=%s",
                    contrato.id_cliente,
                    contrato.id_contrato,
                    qtd_parcelas,
                    "<RetornoErro>" in resultado,
                    "<ParcelaAcordo>" in resultado,
                    mensagem_descarte,
                )
                continue

            array_parcela = extrair_array(resultado, "<ParcelaAcordo>", "</ParcelaAcordo>")
            valor = float(extrair_tag(array_parcela, "<ValorParcela>", "</ValorParcela>"))

            valor_parcelas = 0.0
            if qtd_parcelas > 1:
                resultado = str(resultado).replace(array_parcela, "")
                array_parcela = extrair_array(resultado, "<ParcelaAcordo>", "</ParcelaAcordo>")
                valor_parcelas = float(extrair_tag(array_parcela, "<ValorParcela>", "</ValorParcela>"))

            if not rule.resultado_calculo_parcelas_valido(
                resultados_por_parcela.get(qtd_parcelas, ""),
                qtd_parcelas,
            ):
                ValoresDividas.log.info(
                    "parcelado_descartado_valor_minimo id_cliente=%s id_contrato=%s qtd_parcelas=%s valor_entrada=%s valor_parcelas=%s",
                    contrato.id_cliente,
                    contrato.id_contrato,
                    qtd_parcelas,
                    valor,
                    valor_parcelas,
                )
                continue

            contrato_copia.atualizar_valores(
                valor,
                valor_parcelas,
                contrato.parcelamento_max,
                qtd_parcelas
            )
            # Normaliza data da parcela (primeiro vencimento) para exibir no parcelado
            if data_base:
                contrato_copia.atualizar_data(data_base)

            contratos.append(contrato_copia)

        if contratos:
            contratos_selecionados = rule.selecionar_contratos_parcelados(contratos)
            contratos = (
                contratos_selecionados
                if contratos_selecionados is not None
                else _limitar_contratos_parcelados(contratos)
            )
            max_qtd = max(c.qtd_parcelas for c in contratos)
            for c in contratos:
                c.parcelamento_max = max_qtd
        elif mensagens_descartadas:
            contrato.erro_parcelamento = mensagens_descartadas[-1]

        return contratos

    def soma_valores_sem_desc(xml: str) -> float:
        valor_final = 0
        while "<DividaAtiva>" in xml:
            divida = extrair_array(xml, "<DividaAtiva>", "</DividaAtiva>")

            valor = float(extrair_tag(divida, "<ValorAtualizado>", "</ValorAtualizado>"))


            valor_final += valor

            xml = xml.replace(divida, "")


        return round(valor_final, 2)

    def calculo_entrada(self, contrato: Divida) -> float:
        if contrato.id_cedente in CEDENTES_CALCULO_DETALHE:
            calculo = Calcular(
                contrato.nome_cedente,
                contrato.id_cliente,
                contrato.id_cedente,
                1,
                contrato.valor,
                contrato.xml,
                contrato.data_pagamento
            ).calcular_acordo_com_detalhes()
        else:
            calculo = Calcular(
                contrato.nome_cedente,
                contrato.id_cliente,
                contrato.id_cedente,
                1,
                contrato.valor,
                contrato.xml,
                contrato.data_pagamento
            )

        valor_total = float(extrair_tag(calculo, "<ValorParcela>", "</ValorParcela>"))
        return valor_total * 0.30


