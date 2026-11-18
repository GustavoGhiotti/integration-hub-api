import asyncio, re
from src.infrastructure.external.collectsys import ObterDivida, DadosAcordo, Calcular, ConsultaContratoDetalhe
from src.infrastructure.external.collectsys.cedente_rules import get_cedente_rule
from src.domain.entities import Divida, Acordo
from src.domain.exceptions.collectsys_exception import *
from src.shared.utils.xml_tratamentos import *
from src.domain.entities.contrato import Contrato
from .valores_dividas_service import ValoresDividas
from typing import List, Union, cast
from datetime import date
from src.infrastructure.logging.logger_config import setup_logger
from src.domain.entities.cedentes import (
    CEDENTES_ARC,
    CEDENTES_TETA,
    CEDENTES_TETA_COMUM,
    CEDENTES_CALCULO_DETALHE,
    CEDENTES_COM_PRODUTO,
    CEDENTES_BETA,
    CEDENTES_PARCELAMENTO_MIN_MAX,
    CEDENTES_NU,
    CEDENTES_ZETA,
    BancoBeta,
)
import time

MENSAGEM_NAO_NEGOCIAVEL = "No momento, nao conseguimos negociar este contrato / cliente."

MENSAGEM_SEM_DIVIDA_ATIVA = "No momento, não constam dívidas ativas do cliente em nossa assessoria."
MENSAGEM_SEM_PROPOSTA_AVISTA = "Não possui proposta à vista, somente parcelado."
MENSAGEM_ACORDO_NU_CONTRATO = "Cliente ja possui acordo neste contrato e nao pode fazer um novo acordo."


def consultar_produto_cedente(id_cedente: int, id_cliente: int, id_contrato: int, xml_divida: str) -> str | None:
    produto_xml = extrair_nm_produto(xml_divida)

    consulta = ConsultaContratoDetalhe(id_cliente, id_contrato)
    if id_cedente in CEDENTES_ZETA:
        # A ZETA traz apenas o codigo do produto no detalhe NMPRODUTOCEDENTE; a
        # regra do cedente traduz o codigo para o nome (ex.: "44" -> "EMPRESTIMO").
        codigo = consulta.consultar_produto_zeta()
        return get_cedente_rule(id_cedente).tratar_produto(codigo) or codigo or produto_xml
    if id_cedente in CEDENTES_TETA:
        return consulta.consultar_produto_teta() or produto_xml
    if id_cedente == 60:
        # Na PI a divida traz sempre "PI" em NmProduto; o nome real do
        # produto fica no detalhe PRODUTO do contrato.
        return consulta.consultar_produto_pi() or produto_xml
    if id_cedente in CEDENTES_ARC:
        # A ARC4 usa os detalhes com nomenclatura TETA; o nome do produto esta
        # em PRODUTO NOME TETA.
        return consulta.consultar_produto_arc() or produto_xml
    if id_cedente in CEDENTES_NU:
        # Na Nu o produto e a descricao do bem (modelo da moto), que fica no
        # detalhe DESCRICAO DO BEM do contrato.
        return consulta.consultar_produto_nu() or produto_xml
    # Demais cedentes (sem regra especifica, incluindo o Banco Beta): procura um
    # produto no detalhe do contrato (qualquer detalhe com "PRODUTO" no nome). Nao
    # encontrando, cai no produto da divida e, por fim, no nome da carteira
    # (fallback ja existente no fluxo quando o produto fica vazio).
    return consulta.consultar_nm_produto() or produto_xml


def tipo_negociacao_nu(
    condicao,
    quantidade_parcelas: int | None = None,
    quantidade_parcelas_em_atraso: int | None = None,
) -> str:
    condicao_normalizada = str(condicao or "").strip()

    if not condicao_normalizada.isdigit() or int(condicao_normalizada) <= 0:
        return "parcelas em atraso"

    quantidade_condicao = int(condicao_normalizada)

    if quantidade_parcelas and quantidade_condicao >= quantidade_parcelas:
        return "quitacao"

    if quantidade_parcelas_em_atraso and quantidade_condicao >= quantidade_parcelas_em_atraso:
        return "todas em atraso"

    return "parcial em atraso"


def _valor_original_divida_xml(divida_xml: str) -> float:
    for tag_valor in ("ValorDividaIntegral", "ValorDividaOriginalNovacao", "ValorDividaCalculo"):
        valor_tag = extrair_tag(divida_xml, f"<{tag_valor}>", f"</{tag_valor}>")
        if not valor_tag:
            continue

        try:
            valor_original = float(valor_tag.replace(".", "").replace(",", ".") if "," in valor_tag else valor_tag)
        except ValueError:
            valor_original = 0.0

        if valor_original > 0:
            return valor_original

    return 0.0


def _valor_atualizado_divida_xml(divida_xml: str) -> float:
    valor_tag = extrair_tag(divida_xml, "<ValorAtualizado>", "</ValorAtualizado>")
    if not valor_tag:
        return 0.0

    try:
        return float(
            valor_tag.replace(".", "").replace(",", ".")
            if "," in valor_tag
            else valor_tag
        )
    except ValueError:
        return 0.0


def _parcela_em_atraso_xml(divida_xml: str) -> dict:
    vencimento = extrair_tag(divida_xml, '<DataVencimento>', '</DataVencimento>')
    return {
        "idContrato": int(extrair_tag(divida_xml, '<IdContrato>', '</IdContrato>') or 0),
        "parcela": int(extrair_tag(divida_xml, '<NumeroPrestacao>', '</NumeroPrestacao>') or 0),
        "valor": round(_valor_original_divida_xml(divida_xml), 2),
        "vencimento": re.sub(r'T.*', '', vencimento or ""),
    }


def _contratos_dividas_ativas(
    xml_dividas: str,
    id_cliente: int | None = None,
    id_cedente: int | None = None,
) -> tuple[list[dict], float]:
    xml_restante = extrair_tag(xml_dividas, '<ArrayOfDividaAtiva>', '</ArrayOfDividaAtiva>') or xml_dividas
    contratos_divida: list[dict] = []
    valor_total = 0.0
    # O produto vem do detalhe do contrato (1 chamada SOAP). Sem esse memo, um
    # contrato com N parcelas geraria N consultas identicas.
    produtos_por_contrato: dict[int, str | None] = {}

    while "<DividaAtiva>" in xml_restante:
        divida = extrair_array(xml_restante, '<DividaAtiva>', '</DividaAtiva>')
        if not divida:
            break

        valor_original = _valor_original_divida_xml(divida)
        valor_atualizado = _valor_atualizado_divida_xml(divida)
        id_contrato = int(extrair_tag(divida, '<IdContrato>', '</IdContrato>') or 0)
        numero_contrato_banco = extrair_tag(divida, "<Identificador>", "</Identificador>")
        produto = extrair_nm_produto(divida)
        if id_cliente and id_cedente and id_contrato:
            if id_contrato not in produtos_por_contrato:
                produtos_por_contrato[id_contrato] = consultar_produto_cedente(
                    id_cedente,
                    id_cliente,
                    id_contrato,
                    divida,
                )
            produto = produtos_por_contrato[id_contrato] or produto
        valor_total += valor_original

        contrato_existente = next(
            (contrato for contrato in contratos_divida if contrato["contrato"] == id_contrato),
            None,
        )
        if contrato_existente:
            contrato_existente["valorOriginal"] = round(
                contrato_existente["valorOriginal"] + valor_original,
                2,
            )
            contrato_existente["valorAtualizado"] = round(
                contrato_existente["valorAtualizado"] + valor_atualizado,
                2,
            )
            if numero_contrato_banco and not contrato_existente.get("NumeroContratoBanco"):
                contrato_existente["NumeroContratoBanco"] = numero_contrato_banco
            if produto and not contrato_existente.get("produto"):
                contrato_existente["produto"] = produto
        elif id_contrato:
            dados_contrato = {
                "contrato": id_contrato,
                "valorOriginal": round(valor_original, 2),
                "valorAtualizado": round(valor_atualizado, 2),
            }
            if numero_contrato_banco:
                dados_contrato["NumeroContratoBanco"] = numero_contrato_banco
            if produto:
                dados_contrato["produto"] = produto

            contratos_divida.append(dados_contrato)

        xml_restante = xml_restante.replace(divida, "", 1)

    return contratos_divida, valor_total


def _parcelas_em_atraso_dividas_ativas(xml_dividas: str) -> list[dict]:
    xml_restante = extrair_tag(xml_dividas, '<ArrayOfDividaAtiva>', '</ArrayOfDividaAtiva>') or xml_dividas
    parcelas_por_contrato: dict[int, list[dict]] = {}

    while "<DividaAtiva>" in xml_restante:
        divida = extrair_array(xml_restante, '<DividaAtiva>', '</DividaAtiva>')
        if not divida:
            break

        id_contrato = int(extrair_tag(divida, '<IdContrato>', '</IdContrato>') or 0)
        numero_prestacao = int(extrair_tag(divida, '<NumeroPrestacao>', '</NumeroPrestacao>') or 0)
        atraso = int(extrair_tag(divida, '<Atraso>', '</Atraso>') or 0)

        if id_contrato and numero_prestacao and atraso > 0:
            parcelas_por_contrato.setdefault(id_contrato, [])
            if not any(parcela["parcela"] == numero_prestacao for parcela in parcelas_por_contrato[id_contrato]):
                parcelas_por_contrato[id_contrato].append(_parcela_em_atraso_xml(divida))

        xml_restante = xml_restante.replace(divida, "", 1)

    return [
        {
            "contrato": id_contrato,
            "parcelas": sorted(parcelas, key=lambda parcela: parcela["parcela"]),
        }
        for id_contrato, parcelas in parcelas_por_contrato.items()
    ]


def _valor_total_acordo(valor_entrada: float, valor_parcelas: float, quantidade_parcelas: int) -> float:
    return round(float(valor_entrada) + (float(valor_parcelas) * max(int(quantidade_parcelas) - 1, 0)), 2)


class DadosDivida:
    async def obter_cedentes(cpf_cnpj:str) -> list:
        divida_cobranca, divida_vega = await asyncio.gather(
            asyncio.to_thread(lambda:ObterDivida("Cobrancas").consultar_por_cpf(cpf_cnpj)),
            asyncio.to_thread(lambda:ObterDivida("Vega").consultar_por_cpf(cpf_cnpj))
        )

        mensagens = ["Nenhum cliente localizado com este CPFCNPJ.",
                     "O cliente não possui dívida ativa."]

        if (any(msg in divida_cobranca for msg in mensagens) and
            any(msg in divida_vega for msg in mensagens)):
            raise NenhumaDividaException("No momento, não constam dívidas ativas do cliente em nossa assessoria.")


        dividas = divida_vega + divida_cobranca
        dividas_cedentes = []
        id_cliente = int(extrair_tag(dividas, "<IdCliente>","</IdCliente>"))

        while "<DividaAtiva>" in dividas:
            divida = extrair_array(dividas,'<DividaAtiva>','</DividaAtiva>')

            nome_cedente = extrair_tag(divida, '<NmCedente>', '</NmCedente>')
            id_cedente = int(extrair_tag(divida, '<IdCedente>', '</IdCedente>'))
            id_cliente = int(extrair_tag(divida, '<IdCliente>', '</IdCliente>'))
            id_contrato = int(extrair_tag(divida, '<IdContrato>', '</IdContrato>') or 0)
            tipo_contrato = extrair_tag(divida, '<TipoDivida>', '</TipoDivida>')

            existente = next((c for c in dividas_cedentes if c["idCedente"] == id_cedente), None)

            if not existente:
                dados_cedente = {
                        "cedente": nome_cedente,
                        "idCedente": id_cedente,
                        "idCliente": id_cliente,
                    }
                dividas_cedentes.append(dados_cedente)
            else:
                dados_cedente = existente

            if id_cedente == 99 and id_contrato and not dados_cedente.get("segmento"):
                dados_cedente["segmento"] = ConsultaContratoDetalhe(
                    id_cliente,
                    id_contrato,
                ).consultar_produto_teta()

            if "acordo" in tipo_contrato.lower():
                id_acordo = int(extrair_tag(divida, '<IdAcordo>', '</IdAcordo>'))

                if "Acordos" not in dados_cedente:
                    dados_cedente["Acordos"] = []

                if id_acordo not in [a["idAcordo"] for a in dados_cedente["Acordos"]]:
                    resultado = DadosAcordo(nome_cedente, id_cliente, id_acordo).obter_faturas()
                    contrato = Contrato(resultado, nome_cedente, id_cedente, id_cliente).acordo(1)

                    dados_cedente["Acordos"].append({
                            "grupo": contrato.nome_cedente,
                            "idAcordo": contrato.id_acordo,
                            "valor": contrato.valor,
                            "dataPagamento": contrato.vencimento_boleto
                        })

            else:
                contrato = Contrato(divida, nome_cedente, id_cedente, id_cliente).divida()

                if "Contratos" not in dados_cedente:
                    dados_cedente["Contratos"] = []

                if contrato.id_contrato not in [c["idContrato"] for c in dados_cedente["Contratos"]]:
                    dados_cedente["Contratos"].append({
                                    "idContrato":contrato.id_contrato,
                                    "grupo": contrato.nome_cedente
                                    })

            dividas = dividas.replace(divida, '')

        return dividas_cedentes

    async def obter_dados_divida(id_cliente:int, servidor:str, data:date = None) -> dict:

        dividas = ObterDivida(servidor).consultar_por_id(id_cliente)
        dividas_original = dividas

        mensagens = ["Nenhum cliente localizado com este CPFCNPJ.",
                     "O cliente não possui dívida ativa.",
                     "Cliente não localizado."]

        if (any(msg in dividas for msg in mensagens)):
            raise NenhumaDividaException("No momento, não constam dívidas ativas do cliente em nossa assessoria.")

        nome_cedente = extrair_tag(dividas, '<NmCedente>', '</NmCedente>')
        id_cedente = int(extrair_tag(dividas, '<IdCedente>', '</IdCedente>'))
        id_cliente = int(extrair_tag(dividas, '<IdCliente>', '</IdCliente>'))
        regra_cedente = get_cedente_rule(id_cedente)

        contratos: List[Union[Acordo, Divida]] = []
        parcelas_em_atraso_por_contrato: dict[int, list[dict]] = {}
        total_parcelas_por_contrato: dict[int, int] = {}
        maior_atraso_por_contrato: dict[int, int] = {}
        produtos_por_contrato: dict[int, str] = {}
        produtos_informativos_por_contrato: dict[int, dict] = {}
        numeros_contrato_banco_por_contrato: dict[int, str] = {}
        valor_total_por_contrato: dict[int, float] = {}
        contratos_pi: list[dict] = []
        valor_total_pi = 0.0
        contratos_teta: list[dict] = []
        valor_total_teta = 0.0
        parcelas_em_atraso_agrupadas: list[dict] = []
        if id_cedente == 60:
            contratos_pi, valor_total_pi = _contratos_dividas_ativas(dividas_original, id_cliente, id_cedente)
            if len(contratos_pi) > 1:
                parcelas_em_atraso_agrupadas = _parcelas_em_atraso_dividas_ativas(dividas_original)
        elif id_cedente in CEDENTES_TETA_COMUM:
            contratos_teta, valor_total_teta = _contratos_dividas_ativas(dividas_original, id_cliente, id_cedente)
            if len(contratos_teta) > 1:
                parcelas_em_atraso_agrupadas = _parcelas_em_atraso_dividas_ativas(dividas_original)

        acordos_ativos_nu = (
            NegociacaoDivida._contratos_com_acordo_ativo(dividas_original, nome_cedente, id_cliente)
            if id_cedente == 14
            else set()
        )

        while "<DividaAtiva>" in dividas:
            divida = extrair_array(dividas,'<DividaAtiva>','</DividaAtiva>')

            tipo_contrato = extrair_tag(divida,'<TipoDivida>','</TipoDivida>')

            if "acordo" in tipo_contrato.lower():
                id_acordo = int(extrair_tag(divida, '<IdAcordo>', '</IdAcordo>'))
                numero_prestacao = int(extrair_tag(divida, '<NumeroPrestacao>', '</NumeroPrestacao>'))

                resultado = DadosAcordo(nome_cedente, id_cliente, id_acordo).obter_faturas()

                contrato = Contrato(resultado, nome_cedente, id_cedente, id_cliente).acordo(numero_prestacao)
                contratos.append(contrato)


            else:
                if id_cedente == 60:
                    divida = extrair_tag(dividas, '<ArrayOfDividaAtiva>', '</ArrayOfDividaAtiva>')
                elif id_cedente in CEDENTES_TETA_COMUM and len(contratos_teta) > 1:
                    divida = extrair_tag(dividas, '<ArrayOfDividaAtiva>', '</ArrayOfDividaAtiva>')

                numero_prestacao = int(extrair_tag(divida, '<NumeroPrestacao>', '</NumeroPrestacao>') or 0)
                atraso = int(extrair_tag(divida, '<Atraso>', '</Atraso>') or 0)
                contrato = Contrato(divida, nome_cedente, id_cedente, id_cliente).divida()
                numero_contrato_banco = extrair_tag(divida, "<Identificador>", "</Identificador>")
                valor_divida_integral = extrair_tag(divida, "<ValorDividaIntegral>", "</ValorDividaIntegral>") or "0"
                try:
                    if id_cedente == 60 and valor_total_pi > 0:
                        valor_divida_integral = str(valor_total_pi)
                    elif id_cedente in CEDENTES_TETA_COMUM and len(contratos_teta) > 1 and valor_total_teta > 0:
                        valor_divida_integral = str(valor_total_teta)

                    valor_total_por_contrato[contrato.id_contrato] = (
                        valor_total_por_contrato.get(contrato.id_contrato, 0.0)
                        + float(valor_divida_integral)
                    )
                except ValueError:
                    pass

                nm_produto = produtos_por_contrato.get(contrato.id_contrato)
                if not nm_produto:
                    contexto_produto = regra_cedente.consultar_contexto_produto(
                        id_cliente, contrato.id_contrato
                    )
                    if contexto_produto is not None:
                        nm_produto = contexto_produto.get("produto") or extrair_nm_produto(divida)
                        if contexto_produto.get("informativo"):
                            produtos_informativos_por_contrato[contrato.id_contrato] = contexto_produto
                    else:
                        nm_produto = consultar_produto_cedente(
                            id_cedente,
                            id_cliente,
                            contrato.id_contrato,
                            divida,
                        )
                if nm_produto:
                    produtos_por_contrato[contrato.id_contrato] = nm_produto

                if id_cedente in CEDENTES_COM_PRODUTO and numero_contrato_banco:
                    numeros_contrato_banco_por_contrato[contrato.id_contrato] = numero_contrato_banco
                if id_cedente in CEDENTES_BETA and BancoBeta.eh_produto_cartao(nm_produto) and atraso <= 35:
                    contrato.skip_desconto = True

                total_parcelas_por_contrato[contrato.id_contrato] = max(
                    total_parcelas_por_contrato.get(contrato.id_contrato, 0),
                    numero_prestacao
                )
                maior_atraso_por_contrato[contrato.id_contrato] = max(
                    maior_atraso_por_contrato.get(contrato.id_contrato, 0),
                    atraso,
                )

                if atraso > 0 and numero_prestacao > 0:
                    if contrato.id_contrato not in parcelas_em_atraso_por_contrato:
                        parcelas_em_atraso_por_contrato[contrato.id_contrato] = []

                    if not any(
                        parcela["parcela"] == numero_prestacao
                        for parcela in parcelas_em_atraso_por_contrato[contrato.id_contrato]
                    ):
                        parcelas_em_atraso_por_contrato[contrato.id_contrato].append(
                            _parcela_em_atraso_xml(divida)
                        )

                encontrado = False
                for c in contratos:
                    if c.id_contrato == contrato.id_contrato:
                        c.atualizar_xml(divida)
                        c.numero_prestacao = total_parcelas_por_contrato[contrato.id_contrato]
                        encontrado = True
                        break

                if not encontrado:
                    contrato.numero_prestacao = total_parcelas_por_contrato[contrato.id_contrato]
                    contratos.append(contrato)

                if id_cedente in CEDENTES_TETA_COMUM and len(contratos_teta) > 1:
                    dividas = ""
                    continue

            dividas = dividas.replace(divida, "")

        # Produtos apenas informativos sao definidos pela regra do cedente.
        contratos_calculaveis = [
            contrato
            for contrato in contratos
            if not (
                isinstance(contrato, Divida)
                and (
                    contrato.id_contrato in produtos_informativos_por_contrato
                    or (
                        id_cedente == 14
                        and contrato.id_contrato in acordos_ativos_nu
                    )
                )
            )
        ]

        #Dados não formatados
        try:
            resultados = await ValoresDividas.calcular_valores(contratos_calculaveis, data)
        except RetornoTratadoBeta as erro:
            if id_cedente in CEDENTES_TETA_COMUM and eh_erro_teta_nao_negociavel(str(erro)):
                raise NenhumaDividaException(MENSAGEM_NAO_NEGOCIAVEL)
            if id_cedente in CEDENTES_TETA_COMUM and eh_erro_contrato_nao_encontrado(str(erro)):
                raise NenhumaDividaException(MENSAGEM_SEM_DIVIDA_ATIVA)
            raise

        contratos_dict = {}

        for contrato in contratos:
            if isinstance(contrato, Divida):
                id_contrato = contrato.id_contrato
                contratos_dict[id_contrato] = {
                    "origem": "COLLECTSYS",
                    "contrato": id_contrato,
                    "valorOriginal": {},
                    "propostaSemDesconto": {},
                    "propostaAvista": {}
                }

                contratos_dict[id_contrato]["grupo"] = contrato.nome_cedente
                if id_cedente == 14 and id_contrato in acordos_ativos_nu:
                    parcelas_em_atraso = sorted(
                        parcelas_em_atraso_por_contrato.get(id_contrato, []),
                        key=lambda parcela: parcela["parcela"],
                    )
                    vencimentos = [
                        parcela["vencimento"]
                        for parcela in parcelas_em_atraso
                        if parcela.get("vencimento")
                    ]
                    contratos_dict[id_contrato]["valorOriginal"] = {
                        "valor": round(
                            sum(float(parcela.get("valor") or 0) for parcela in parcelas_em_atraso),
                            2,
                        ),
                        "atraso": maior_atraso_por_contrato.get(id_contrato, 0),
                        "atrasadoDesde": min(vencimentos) if vencimentos else "",
                        "parcelasEmAtraso": parcelas_em_atraso,
                        "quantidadeParcelasEmAtraso": len(parcelas_em_atraso),
                        "quantidadeParcelas": total_parcelas_por_contrato.get(
                            id_contrato,
                            len(parcelas_em_atraso),
                        ),
                    }
                if id_cedente == 60 and contratos_pi:
                    if len(contratos_pi) > 1:
                        contratos_dict[id_contrato].pop("contrato", None)
                    contratos_dict[id_contrato]["quantidadeContratos"] = len(contratos_pi)
                    contratos_dict[id_contrato]["contratosUtilizados"] = contratos_pi
                elif id_cedente in CEDENTES_TETA_COMUM and contratos_teta:
                    if len(contratos_teta) > 1:
                        contratos_dict[id_contrato].pop("contrato", None)
                    contratos_dict[id_contrato]["quantidadeContratos"] = len(contratos_teta)
                    contratos_dict[id_contrato]["contratosUtilizados"] = contratos_teta

                produto = produtos_por_contrato.get(id_contrato) or extrair_nm_produto(contrato.xml)
                produto = regra_cedente.descrever_produto(contrato.xml, produto)
                if produto:
                    contratos_dict[id_contrato]["produto"] = produto

                if id_contrato in produtos_informativos_por_contrato:
                    parcelas_em_atraso = sorted(
                        parcelas_em_atraso_por_contrato.get(id_contrato, []),
                        key=lambda parcela: parcela["parcela"],
                    )
                    regra_cedente.aplicar_produto_informativo_verifica(
                        contratos_dict[id_contrato],
                        produtos_informativos_por_contrato[id_contrato],
                        parcelas_em_atraso,
                        total_parcelas_por_contrato.get(id_contrato, len(parcelas_em_atraso)),
                    )

                if id_cedente in CEDENTES_COM_PRODUTO:
                    teta_agrupado = id_cedente in CEDENTES_TETA_COMUM and len(contratos_teta) > 1
                    if not teta_agrupado:
                        numero_contrato_banco = numeros_contrato_banco_por_contrato.get(id_contrato)
                        if numero_contrato_banco:
                            contratos_dict[id_contrato]["NumeroContratoBanco"] = numero_contrato_banco
                    if id_cedente == 81:
                        contratos_dict[id_contrato]["ValorTotalContrato"] = round(
                            valor_total_por_contrato.get(id_contrato, 0.0),
                            2,
                        )

            else:
                if contrato.id_acordo not in contratos_dict:
                    contratos_dict[contrato.id_acordo] = {
                                "origem": "COLLECTSYS",
                                "grupo": contrato.nome_cedente,
                                "contrato": contrato.id_contrato,
                                "parcelas": []
                                }

                item = {
                    "idAcordo": contrato.id_acordo,
                    "valor": contrato.valor,
                    "parcela": contrato.numero_parcelas,
                    "dataVencimento": contrato.vencimento_boleto
                }

                contratos_dict[contrato.id_acordo]["parcelas"].append(item)

        possui_acordo = any(isinstance(contrato, Acordo) for contrato in contratos)

        for item in resultados:
            resultado = item["resultado"]
            tipo = item["tipo"]
            id_contrato = item["idContrato"]

            if id_contrato not in contratos_dict:
                continue

            possui_dados_validos = any(
                bool(valor.get("parcelas"))
                or bool(valor.get("valorOriginal"))
                or bool(valor.get("propostaSemDesconto"))
                or bool(valor.get("propostaAvista"))
                for valor in contratos_dict.values()
                if isinstance(valor, dict)
            )

            if not possui_dados_validos and id_cedente in CEDENTES_TETA_COMUM and eh_erro_contrato_nao_encontrado(resultado):
                raise NenhumaDividaException(MENSAGEM_SEM_DIVIDA_ATIVA)
            if not possui_dados_validos and id_cedente in CEDENTES_TETA_COMUM and eh_erro_teta_nao_negociavel(resultado):
                raise NenhumaDividaException(MENSAGEM_NAO_NEGOCIAVEL)

            erro = extrair_tag(resultado, "<RetornoErro>", "</RetornoErro>")
            if erro:
                mensagem = extrair_tag(resultado, "<Mensagem>", "</Mensagem>")
                if possui_acordo and eh_erro_divida_nao_selecionada(mensagem or resultado):
                    contratos_dict.pop(id_contrato, None)
                    continue
                if id_cedente in CEDENTES_TETA_COMUM and eh_erro_teta_nao_negociavel(mensagem or resultado):
                    raise NenhumaDividaException(MENSAGEM_NAO_NEGOCIAVEL)
                if id_cedente in CEDENTES_TETA_COMUM and eh_erro_contrato_nao_encontrado(mensagem or resultado):
                    raise NenhumaDividaException(MENSAGEM_SEM_DIVIDA_ATIVA)
                if id_cedente in CEDENTES_TETA_COMUM and tipo == "comDesconto":
                    contratos_dict[id_contrato]["propostaAvista"] = {
                        "mensagem": MENSAGEM_SEM_PROPOSTA_AVISTA
                    }
                    continue
                if possui_dados_validos:
                    continue
                if (
                    id_cedente in CEDENTES_TETA_COMUM
                    and tipo == "comDesconto"
                    and mensagem
                    and "plano mínimo é" in mensagem.lower()
                ):
                    minimo_match = re.search(r"plano m[íi]nimo é\s*(\d+)", mensagem, re.IGNORECASE)
                    if minimo_match:
                        contratos_dict[id_contrato]["propostaAvista"] = {
                            "mensagem": f"o minimo de parcelas para esse contrato = {minimo_match.group(1)}"
                        }
                    continue
                elif id_cedente in (81, 104) and "Falha ao calcular dívida" in mensagem:
                    mensagem = "Contrato não pode ser negociado no momento."
                    return {
                    "origem": "COLLECTSYS",
                    "mensagem": mensagem
    }
                return {
                    "origem": "COLLECTSYS",
                    "mensagem": mensagem
    }

            if tipo == "semDesconto":

                valor_sem_desconto = ValoresDividas.soma_valores_sem_desc(resultado)
                valor_original = round(valor_total_por_contrato.get(id_contrato, valor_sem_desconto), 2)
                contratos_dict[id_contrato]["valorAtualizado"] = round(valor_sem_desconto, 2)

                # No calculo agrupado, o retorno mantem as DividaAtiva com o
                # IdContrato. Atualiza cada item de contratosUtilizados com o
                # valor calculado correspondente, sem rateio ou aproximacao.
                contratos_calculados, _ = _contratos_dividas_ativas(resultado)
                atualizados_por_contrato = {
                    item["contrato"]: item["valorAtualizado"]
                    for item in contratos_calculados
                }
                for contrato_utilizado in contratos_dict[id_contrato].get("contratosUtilizados", []):
                    contrato_utilizado_id = contrato_utilizado.get("contrato")
                    if contrato_utilizado_id in atualizados_por_contrato:
                        contrato_utilizado["valorAtualizado"] = atualizados_por_contrato[contrato_utilizado_id]

                atraso = int(extrair_tag(resultado, "<Atraso>", "</Atraso>") or 0)
                vencimento =  re.sub(r'T.*', '', extrair_tag(resultado,'<DataVencimento>', '</DataVencimento>'))
                parcelas_em_atraso = parcelas_em_atraso_por_contrato.get(id_contrato, [])
                total_parcelas = total_parcelas_por_contrato.get(id_contrato, 0)
                quantidade_parcelas = total_parcelas
                eh_agrupado = (
                    (id_cedente == 60 and len(contratos_pi) > 1)
                    or (id_cedente in CEDENTES_TETA_COMUM and len(contratos_teta) > 1)
                )

                contratos_dict[id_contrato]["propostaSemDesconto"] = {
                    "valor": valor_sem_desconto
                }

                if eh_agrupado:
                    quantidade_parcelas_agrupadas = sum(
                        len(item["parcelas"]) for item in parcelas_em_atraso_agrupadas
                    )
                    contratos_dict[id_contrato]["valorOriginal"] = {
                        "valor": valor_original,
                        "atraso": atraso,
                        "atrasadoDesde": vencimento,
                        "parcelasEmAtraso": parcelas_em_atraso_agrupadas,
                        "quantidadeParcelasEmAtraso": quantidade_parcelas_agrupadas,
                        "quantidadeParcelas": quantidade_parcelas_agrupadas
                    }
                elif id_cedente in (14, 43, 65, 81, 104):
                    contratos_dict[id_contrato]["valorOriginal"] = {
                        "valor": valor_original,
                        "atraso": atraso,
                        "atrasadoDesde": vencimento,
                        "parcelasEmAtraso": sorted(
                            parcelas_em_atraso,
                            key=lambda parcela: parcela["parcela"],
                        ),
                        "quantidadeParcelasEmAtraso": len(parcelas_em_atraso),
                        "quantidadeParcelas": quantidade_parcelas
                    }
                else:
                    contratos_dict[id_contrato]["valorOriginal"] = {
                        "valor": valor_original,
                        "atraso": atraso,
                        "atrasadoDesde": vencimento
                    }

            elif tipo == "comDesconto":
                valor_str = extrair_tag(resultado, "<ValorParcela>", "</ValorParcela>")

                if valor_str is None:
                    if id_cedente in CEDENTES_TETA_COMUM:
                        contratos_dict[id_contrato]["propostaAvista"] = {
                            "mensagem": MENSAGEM_SEM_PROPOSTA_AVISTA
                        }
                        continue
                    if id_cedente in (81, 104):
                        contratos_dict[id_contrato]["propostaAvista"] = {
                            "mensagem": "Contrato nao pode ser negociado no momento."
                        }
                        continue
                    raise ValueError(f"ValorParcela não encontrado ou vazio no XML. XML recebido: {resultado}")

                try:
                    valor = float(valor_str.replace(",", "."))
                except ValueError:
                    if id_cedente in (81, 104):
                        contratos_dict[id_contrato]["propostaAvista"] = {
                            "mensagem": "Contrato nao pode ser negociado no momento."
                        }
                        continue
                    raise ValueError(f"ValorParcela inválido ({valor_str}) no XML. XML recebido: {resultado}")

                valor = float(extrair_tag(resultado, "<ValorParcela>", "</ValorParcela>"))
                pagamento =  re.sub(r'T.*', '', extrair_tag(resultado,'<DataParcela>', '</DataParcela>'))

                contratos_dict[id_contrato]["propostaAvista"] = {
                    "valor": valor,
                    "pagamento": pagamento,
                }

        for contrato in contratos:
            if not isinstance(contrato, Divida):
                continue
            if contrato.id_cedente not in (81, 104):
                continue
            if not getattr(contrato, "skip_desconto", False):
                continue

            proposta_atual = contratos_dict.get(contrato.id_contrato, {}).get("propostaAvista")
            if proposta_atual:
                continue

            proposta_avista = ValoresDividas.proposta_avista_cartao_35(contrato)
            if not proposta_avista:
                continue

            proposta_avista_formatada = {
                "valor": proposta_avista["valorEntrada"],
                "pagamento": proposta_avista["dataPagamento"].isoformat(),
            }
            if proposta_avista.get("boleto"):
                proposta_avista_formatada["boleto"] = proposta_avista["boleto"]

            contratos_dict[contrato.id_contrato]["propostaAvista"] = proposta_avista_formatada

        contratos_dict = {
            chave: valor
            for chave, valor in contratos_dict.items()
            if (
                not isinstance(valor, dict)
                or bool(valor.get("parcelas"))
                or bool(valor.get("valorOriginal"))
                or bool(valor.get("propostaSemDesconto"))
                or bool(valor.get("propostaAvista"))
            )
        }

        return contratos_dict


class NegociacaoDivida:
    log = setup_logger("collectsys_parcelado", "collectsys_parcelado.log")

    @staticmethod
    def _ids_contrato_acordo_xml(acordo_xml: str) -> set[int]:
        ids_contrato = set()
        originais_acordo = extrair_tag(acordo_xml or "", "<OriginaisAcordo>", "</OriginaisAcordo>")
        originais = originais_acordo or acordo_xml or ""

        while "<OriginalAcordo>" in originais:
            original = extrair_array(originais, "<OriginalAcordo>", "</OriginalAcordo>")
            if not original:
                break

            id_contrato = extrair_tag(original, "<IdContrato>", "</IdContrato>")
            try:
                if id_contrato:
                    ids_contrato.add(int(id_contrato))
            except ValueError:
                pass

            originais = originais.replace(original, "", 1)

        if not ids_contrato and originais_acordo:
            for id_contrato in re.findall(r"<IdContrato>(\d+)</IdContrato>", originais_acordo):
                ids_contrato.add(int(id_contrato))

        if ids_contrato:
            return ids_contrato

        id_contrato = extrair_tag(acordo_xml or "", "<IdContrato>", "</IdContrato>")
        try:
            if id_contrato:
                ids_contrato.add(int(id_contrato))
        except ValueError:
            pass

        return ids_contrato

    @staticmethod
    def _contratos_com_acordo_ativo(dividas: str, nome_cedente: str, id_cliente: int) -> set[int]:
        contratos_com_acordo = set()
        dividas_xml = dividas or ""

        while "<DividaAtiva>" in dividas_xml:
            divida = extrair_array(dividas_xml, "<DividaAtiva>", "</DividaAtiva>")
            if not divida:
                break

            tipo_divida = (extrair_tag(divida, "<TipoDivida>", "</TipoDivida>") or "").lower()
            id_acordo = extrair_tag(divida, "<IdAcordo>", "</IdAcordo>")

            try:
                id_acordo_int = int(id_acordo or 0)
            except ValueError:
                id_acordo_int = 0

            if "acordo" in tipo_divida and id_acordo_int > 0:
                contratos_com_acordo.update(NegociacaoDivida._ids_contrato_acordo_xml(divida))

                try:
                    acordo_xml = DadosAcordo(nome_cedente, id_cliente, id_acordo_int).obter_acordo()
                    contratos_com_acordo.update(NegociacaoDivida._ids_contrato_acordo_xml(acordo_xml))
                except Exception:
                    pass

                try:
                    faturas_xml = DadosAcordo(nome_cedente, id_cliente, id_acordo_int).obter_faturas()
                    contratos_com_acordo.update(NegociacaoDivida._ids_contrato_acordo_xml(faturas_xml))
                except Exception:
                    pass

            dividas_xml = dividas_xml.replace(divida, "", 1)

        return contratos_com_acordo

    @staticmethod
    def _dividas_por_contrato(dividas: str) -> dict[int, str]:
        dividas_por_contrato: dict[int, str] = {}
        dividas_xml = dividas or ""

        while "<DividaAtiva>" in dividas_xml:
            divida = extrair_array(dividas_xml, "<DividaAtiva>", "</DividaAtiva>")
            if not divida:
                break

            try:
                id_contrato = int(extrair_tag(divida, "<IdContrato>", "</IdContrato>") or 0)
            except ValueError:
                id_contrato = 0

            if id_contrato:
                dividas_por_contrato[id_contrato] = dividas_por_contrato.get(id_contrato, "") + divida

            dividas_xml = dividas_xml.replace(divida, "", 1)

        return dividas_por_contrato

    @staticmethod
    def _mensagem_acordo_ativo_produto(
        dividas: str,
        nome_cedente: str,
        id_cliente: int,
        xml_divida: str,
        regra_cedente,
    ) -> str | None:
        """Cedentes que permitem apenas um acordo por produto.

        O bloqueio e por produto, nao por contrato: um acordo ativo em qualquer
        contrato do mesmo produto impede um acordo novo.
        """
        produto = regra_cedente.identificar_produto(xml_divida)
        if not produto:
            return None

        contratos_com_acordo = NegociacaoDivida._contratos_com_acordo_ativo(
            dividas,
            nome_cedente,
            id_cliente,
        )
        if not contratos_com_acordo:
            return None

        dividas_por_contrato = NegociacaoDivida._dividas_por_contrato(dividas)
        for id_contrato_acordo in contratos_com_acordo:
            produto_acordo = regra_cedente.identificar_produto(
                dividas_por_contrato.get(id_contrato_acordo, "")
            )
            if produto_acordo == produto:
                return regra_cedente.mensagem_acordo_ativo_produto(produto)

        return None

    @staticmethod
    def _contrato_possui_acordo_ativo(dividas: str, id_contrato: int) -> bool:
        dividas_xml = dividas or ""

        while "<DividaAtiva>" in dividas_xml:
            divida = extrair_array(dividas_xml, "<DividaAtiva>", "</DividaAtiva>")
            if not divida:
                break

            tipo_divida = (extrair_tag(divida, "<TipoDivida>", "</TipoDivida>") or "").lower()
            id_contrato_divida = extrair_tag(divida, "<IdContrato>", "</IdContrato>")
            id_acordo = extrair_tag(divida, "<IdAcordo>", "</IdAcordo>")

            try:
                acordo_mesmo_contrato = (
                    "acordo" in tipo_divida
                    and id_contrato_divida
                    and int(id_contrato_divida) == int(id_contrato)
                    and id_acordo
                    and int(id_acordo) > 0
                )
            except ValueError:
                acordo_mesmo_contrato = False

            if acordo_mesmo_contrato:
                return True

            dividas_xml = dividas_xml.replace(divida, "", 1)

        return False

    @staticmethod
    def _condicao_informada(condicao) -> bool:
        if isinstance(condicao, bool):
            return False

        condicao_normalizada = str(condicao or "").strip()
        if not condicao_normalizada.isdigit():
            return False

        return int(condicao_normalizada) > 0

    @staticmethod
    def _mensagem_plano_indisponivel(parcela_min: int | None, parcela_max: int | None, complemento: str = "") -> str:
        return (
            f"Plano nao disponivel{complemento}. Plano minimo e de {parcela_min or 1} "
            f"e o maximo e {parcela_max or parcela_min or 1}"
        )

    @staticmethod
    def _erro_valor_entrada_beta(resultado: str) -> NenhumaDividaException | None:
        if "VALOR" not in (resultado or "").upper():
            return None

        valor_min_erro, valor_max_erro = capturar_intervalo_valor_entrada_cedente_81(resultado)
        if valor_min_erro is None and valor_max_erro is None:
            return None

        valor_minimo_erro = max(float(valor_min_erro or 0), 50.0)
        valor_maximo_erro = float(valor_max_erro or 0)

        if valor_maximo_erro >= valor_minimo_erro:
            return NenhumaDividaException(
                f"Valor de entrada deve ser entre {str(round(valor_minimo_erro, 2)).replace('.', ',')} e {str(round(valor_maximo_erro, 2)).replace('.', ',')}"
            )

        return NenhumaDividaException(
            f"Valor de entrada deve ser no minimo {str(round(valor_minimo_erro, 2)).replace('.', ',')}"
        )

    async def negociacao_parcelado(id_cliente:int, id_contrato:int) -> dict:
        inicio_total = time.perf_counter()
        dividas = ObterDivida("COBRANCA").consultar_por_id(id_cliente)

        mensagens = ["Nenhum cliente localizado com este CPFCNPJ.",
                     "O cliente não possui dívida ativa.",
                     "Cliente não localizado."]

        if (any(msg in dividas for msg in mensagens)):
            raise NenhumaDividaException("No momento, não constam dívidas ativas do cliente em nossa assessoria.")

        ms_obter_divida = int((time.perf_counter() - inicio_total) * 1000)
        xml_divida = ""
        nm_produto = None
        numero_contrato_banco = None
        nome_cedente = extrair_tag(dividas, '<NmCedente>', '</NmCedente>')
        id_cedente = int(extrair_tag(dividas, '<IdCedente>', '</IdCedente>'))
        regra_cedente = get_cedente_rule(id_cedente)
        contratos_teta, _ = (
            _contratos_dividas_ativas(dividas, id_cliente, id_cedente)
            if id_cedente in CEDENTES_TETA_COMUM
            else ([], 0.0)
        )

        if (
            id_cedente == 14
            and int(id_contrato) in NegociacaoDivida._contratos_com_acordo_ativo(dividas, nome_cedente, id_cliente)
        ):
            raise NenhumaDividaException(MENSAGEM_ACORDO_NU_CONTRATO)

        # O laco abaixo consome `dividas`; guarda a listagem completa para as
        # validacoes que precisam olhar os outros contratos do cliente.
        dividas_cliente = dividas

        if id_cedente == 60 or (id_cedente in CEDENTES_TETA_COMUM and len(contratos_teta) > 1):
            xml_divida = extrair_tag(dividas, '<ArrayOfDividaAtiva>', '</ArrayOfDividaAtiva>')
        else:
            while "<DividaAtiva>" in dividas:
                divida = extrair_array(dividas,'<DividaAtiva>','</DividaAtiva>')

                id_contrato_divida = int(extrair_tag(divida, "<IdContrato>","</IdContrato>"))

                if int(id_contrato) == id_contrato_divida:
                    xml_divida += divida

                dividas = dividas.replace(divida, "")

        if xml_divida == '':
            raise NenhumaDividaException("No momento, não constam dívidas ativas do cliente em nossa assessoria.")

        mensagem_produtos_mesclados = regra_cedente.mensagem_produtos_mesclados(xml_divida)
        if mensagem_produtos_mesclados:
            raise NenhumaDividaException(mensagem_produtos_mesclados)

        mensagem_acordo_produto = NegociacaoDivida._mensagem_acordo_ativo_produto(
            dividas_cliente,
            nome_cedente,
            id_cliente,
            xml_divida,
            regra_cedente,
        )
        if mensagem_acordo_produto:
            raise NenhumaDividaException(mensagem_acordo_produto)

        contexto_produto = regra_cedente.consultar_contexto_produto(
            id_cliente, int(id_contrato)
        )
        if contexto_produto and contexto_produto.get("informativo"):
            return regra_cedente.montar_produto_informativo_parcelado(
                contexto_produto, nome_cedente, id_cliente, id_contrato
            )

        nm_produto = (contexto_produto or {}).get("produto") or extrair_nm_produto(xml_divida)
        nm_produto = regra_cedente.descrever_produto(xml_divida, nm_produto)
        numero_contrato_banco = extrair_tag(xml_divida, "<Identificador>", "</Identificador>")

        if id_cedente in (65,73,81, 104):
            valor_str = extrair_tag(xml_divida,'<ValorDividaIntegral>','</ValorDividaIntegral>')

        else:
            valor_str = '0.0' #extrair_tag(xml_divida,'<ValorAtualizado>','</ValorAtualizado>') or extrair_tag(xml_divida,'<ValorDividaIntegral>','</ValorDividaIntegral>')

        if not valor_str:
            raise NenhumaDividaException("No momento, não constam dívidas ativas do cliente em nossa assessoria.")

        valor = float(valor_str)

        contrato = Contrato(xml_divida, nome_cedente, id_cedente, id_cliente, valor).divida()
        valor_min = None
        valor_max = None
        parcela_min = None
        cartao_35 = None

        if contexto_produto and contexto_produto.get("somente_avista"):
            # Produto consignado sem liberacao de IDT_20: somente a vista, sem
            # oferecer parcelamento/reparcelamento do contrato inteiro.
            contrato.parcelamento_max = 1
            ms_parc_max = 0

        elif contrato.id_cedente not in (33, 14, *CEDENTES_PARCELAMENTO_MIN_MAX):
            inicio_parc_max = time.perf_counter()
            await ValoresDividas.obter_parcelamento_max(contrato)
            ms_parc_max = int((time.perf_counter() - inicio_parc_max) * 1000)

        elif contrato.id_cedente in CEDENTES_PARCELAMENTO_MIN_MAX:
            inicio_parc_max = time.perf_counter()
            if contrato.id_cedente in CEDENTES_COM_PRODUTO and not nm_produto:
                nm_produto = consultar_produto_cedente(
                    contrato.id_cedente,
                    id_cliente,
                    id_contrato,
                    xml_divida,
                )
            atraso = int(extrair_tag(xml_divida, "<Atraso>","</Atraso>") or 0)
            if contrato.id_cedente in CEDENTES_BETA and BancoBeta.eh_produto_cartao(nm_produto) and atraso <= 35:
                cartao_35 = 'SIM'
            if cartao_35 != 'SIM':
                calculo_parcelamento = Calcular(
                    contrato.nome_cedente,
                    contrato.id_cliente,
                    contrato.id_cedente,
                    min(contrato.parcelamento_max, 36),
                    contrato.valor,
                    contrato.xml,
                    contrato.data_pagamento
                )
                retorno_parcelamento = calculo_parcelamento.calcular_acordo_com_detalhes(
                    parcelado="VALOR ENTRADA",
                    cartao_35=cartao_35,
                )
                NegociacaoDivida.log.info(
                    "beta_retorno_parcelamento id_cliente=%s id_contrato=%s produto=%s atraso=%s cartao_35=%s retorno=%s",
                    id_cliente,
                    id_contrato,
                    nm_produto,
                    atraso,
                    cartao_35,
                    retorno_parcelamento,
                )
                if not isinstance(retorno_parcelamento, tuple) or len(retorno_parcelamento) != 5:
                    raise CollectSysException(mensagem=str(retorno_parcelamento))

                valor_min, valor_max, parcela_min, parcela_max, cartao_35 = retorno_parcelamento
                contrato.parcelamento_max = parcela_max
                if contrato.id_cedente in CEDENTES_BETA and valor_max:
                    contrato.valor = valor_max
            ms_parc_max = int((time.perf_counter() - inicio_parc_max) * 1000)

        else:
            contrato.parcelamento_max = 1
            ms_parc_max = 0

        inicio_parcelas = time.perf_counter()
        contratos_parcelados = await ValoresDividas.valores_parcelados(
            contrato,
            valor_min,
            valor_max,
            cartao_35,
            parcela_min,
        )
        ms_parcelas = int((time.perf_counter() - inicio_parcelas) * 1000)
        if contratos_parcelados == []:
            ms_total = int((time.perf_counter() - inicio_total) * 1000)
            mensagem_propostas = getattr(contrato, "erro_parcelamento", None) or "Não a propostas no momento"
            NegociacaoDivida.log.info(
                "propostas_parcelado_done id_cliente=%s id_contrato=%s id_cedente=%s ms_total=%s ms_obter_divida=%s ms_parc_max=%s ms_parcelas=%s propostas=%s",
                id_cliente,
                id_contrato,
                id_cedente,
                ms_total,
                ms_obter_divida,
                ms_parc_max,
                ms_parcelas,
                0,
            )
            resposta = {"origem": "COLLECTSYS",
                "nomeCedente": nome_cedente,
                "idCliente": id_cliente,
                "contrato": id_contrato,
                "propostas": mensagem_propostas}
            if nm_produto:
                resposta["produto"] = nm_produto
            if id_cedente in CEDENTES_COM_PRODUTO:
                teta_agrupado = id_cedente in CEDENTES_TETA_COMUM and len(contratos_teta) > 1
                if numero_contrato_banco and not teta_agrupado:
                    resposta["NumeroContratoBanco"] = numero_contrato_banco
                if id_cedente in CEDENTES_TETA_COMUM and contratos_teta:
                    if len(contratos_teta) > 1:
                        resposta.pop("contrato", None)
                    resposta["quantidadeContratos"] = len(contratos_teta)
                    resposta["contratosUtilizados"] = contratos_teta
            return resposta

        propostas_parcelamento = []
        for contrato_parcela in contratos_parcelados:
            contrato_parcela = cast(Divida, contrato_parcela)

            proposta = {
                "valorEntrada":contrato_parcela.valor,
                "valorParcelas":contrato_parcela.valor_parcelas,
                "qtdParcelas":contrato_parcela.qtd_parcelas,
                "parcelamentoMax": contrato_parcela.parcelamento_max,
                "dataPagamento": contrato_parcela.data_pagamento
            }
            if contrato_parcela.qtd_parcelas > 1:
                proposta["valorTotalAcordo"] = _valor_total_acordo(
                    contrato_parcela.valor,
                    contrato_parcela.valor_parcelas,
                    contrato_parcela.qtd_parcelas,
                )
            if hasattr(contrato_parcela, "boleto"):
                proposta["boleto"] = contrato_parcela.boleto

            if id_cedente in (81, 104):
                detalhe_proposta = BancoBeta.detalhe_proposta(
                    nm_produto,
                    contrato_parcela.qtd_parcelas,
                    cartao_35,
                )
                if detalhe_proposta:
                    proposta.update(detalhe_proposta)

            propostas_parcelamento.append(proposta)

        ms_total = int((time.perf_counter() - inicio_total) * 1000)
        NegociacaoDivida.log.info(
            "propostas_parcelado_done id_cliente=%s id_contrato=%s id_cedente=%s ms_total=%s ms_obter_divida=%s ms_parc_max=%s ms_parcelas=%s propostas=%s",
            id_cliente,
            id_contrato,
            id_cedente,
            ms_total,
            ms_obter_divida,
            ms_parc_max,
            ms_parcelas,
            len(propostas_parcelamento),
        )
        resposta = {"origem": "COLLECTSYS",
                "nomeCedente": nome_cedente,
                "idCliente": id_cliente,
                "contrato": id_contrato,
                "propostas": propostas_parcelamento}
        if nm_produto:
            resposta["produto"] = nm_produto
        if id_cedente in CEDENTES_COM_PRODUTO:
            teta_agrupado = id_cedente in CEDENTES_TETA_COMUM and len(contratos_teta) > 1
            if numero_contrato_banco and not teta_agrupado:
                resposta["NumeroContratoBanco"] = numero_contrato_banco

            if id_cedente in CEDENTES_TETA_COMUM and contratos_teta:
                if len(contratos_teta) > 1:
                    resposta.pop("contrato", None)
                resposta["quantidadeContratos"] = len(contratos_teta)
                resposta["contratosUtilizados"] = contratos_teta
        return resposta


    async def proposta_cliente(id_cliente:int,id_contrato:int,valor_entrada:float, plano:int,
                               data_vencimento: date,gerar_acordo:bool, condicao=None ) -> dict:
        valor_entrada_informada = valor_entrada
        dividas = ObterDivida("COBRANCA").consultar_por_id(id_cliente)

        mensagens = ["Nenhum cliente localizado com este CPFCNPJ.",
                     "O cliente não possui dívida ativa.",
                     "Cliente não localizado."]

        if (any(msg in dividas for msg in mensagens)):
            raise NenhumaDividaException("No momento, não constam dívidas ativas do cliente em nossa assessoria.")

        nome_cedente = extrair_tag(dividas, "<NmCedente>", "</NmCedente>")
        id_cedente = int(extrair_tag(dividas, "<IdCedente>", "</IdCedente>"))
        regra_cedente = get_cedente_rule(id_cedente)
        contratos_teta, _ = (
            _contratos_dividas_ativas(dividas, id_cliente, id_cedente)
            if id_cedente in CEDENTES_TETA_COMUM
            else ([], 0.0)
        )
        xml_divida = ""
        maior_numero_prestacao = 0
        parcelas_em_atraso = set()
        # O laco abaixo consome `dividas`; guarda a listagem completa para as
        # validacoes que precisam olhar os outros contratos do cliente.
        dividas_cliente = dividas

        if (
            id_cedente == 14
            and int(id_contrato) in NegociacaoDivida._contratos_com_acordo_ativo(dividas, nome_cedente, id_cliente)
        ):
            raise NenhumaDividaException(MENSAGEM_ACORDO_NU_CONTRATO)

        if id_cedente in (60, 71) or (id_cedente in CEDENTES_TETA_COMUM and len(contratos_teta) > 1):
            xml_divida = extrair_tag(dividas, '<ArrayOfDividaAtiva>', '</ArrayOfDividaAtiva>')
        else:
            while "<DividaAtiva>" in dividas:
                divida = extrair_array(dividas,'<DividaAtiva>','</DividaAtiva>')

                id_contrato_divida = int(extrair_tag(divida, "<IdContrato>","</IdContrato>"))
                try:
                    if int(id_contrato) != id_contrato_divida:
                        raise

                    # Alguns cedentes negociam apenas parcelas em atraso. Delta exige
                    # todas as parcelas do contrato para acordos parcelados.
                    atraso = int(extrair_tag(divida, "<Atraso>","</Atraso>") or 0)
                    if id_cedente in (71, 70) and atraso < 0:
                        raise

                    numero_prestacao = int(extrair_tag(divida, "<NumeroPrestacao>", "</NumeroPrestacao>") or 0)
                    maior_numero_prestacao = max(maior_numero_prestacao, numero_prestacao)
                    if atraso > 0 and numero_prestacao > 0:
                        parcelas_em_atraso.add(numero_prestacao)
                    xml_divida += divida
                except:
                    pass
                finally:
                    dividas = dividas.replace(divida, "")


        if xml_divida == '':
            raise NenhumaDividaException("No momento, não constam dívidas ativas do cliente em nossa assessoria.")

        # O limite de parcelas pode variar por produto do cedente, por isso e
        # resolvido somente depois de identificar a divida do contrato.
        limite_max_parcelas = regra_cedente.limite_parcelas_divida(xml_divida)
        if limite_max_parcelas is not None and plano > limite_max_parcelas:
            raise NenhumaDividaException(
                NegociacaoDivida._mensagem_plano_indisponivel(1, limite_max_parcelas)
            )

        mensagem_entrada_invalida = regra_cedente.mensagem_valor_entrada_invalido(
            valor_entrada_informada,
            plano,
        )
        if mensagem_entrada_invalida:
            raise NenhumaDividaException(mensagem_entrada_invalida)

        mensagem_produtos_mesclados = regra_cedente.mensagem_produtos_mesclados(xml_divida)
        if mensagem_produtos_mesclados:
            raise NenhumaDividaException(mensagem_produtos_mesclados)

        mensagem_acordo_produto = NegociacaoDivida._mensagem_acordo_ativo_produto(
            dividas_cliente,
            nome_cedente,
            id_cliente,
            xml_divida,
            regra_cedente,
        )
        if mensagem_acordo_produto:
            raise NenhumaDividaException(mensagem_acordo_produto)

        mensagem_negociacao_parcial = regra_cedente.mensagem_negociacao_parcial_invalida(
            condicao,
            plano,
            maior_numero_prestacao,
        )
        if mensagem_negociacao_parcial:
            raise NenhumaDividaException(mensagem_negociacao_parcial)

        if id_cedente in (65, 73):
            valor_str = extrair_tag(xml_divida,'<ValorDividaIntegral>','</ValorDividaIntegral>')
        else:
            valor_str = '0.0' #extrair_tag(xml_divida,'<ValorAtualizado>','</ValorAtualizado>') or extrair_tag(xml_divida,'<ValorDividaIntegral>','</ValorDividaIntegral>')

        if not valor_str:
            raise NenhumaDividaException("No momento, não constam dívidas ativas do cliente em nossa assessoria.")


        valor = float(valor_str)

        contrato = Contrato(xml_divida, nome_cedente, id_cedente, id_cliente, valor).divida()
        nm_produto = extrair_nm_produto(xml_divida)
        numero_contrato_banco = extrair_tag(xml_divida, "<Identificador>", "</Identificador>")
        contexto_produto = regra_cedente.consultar_contexto_produto(
            id_cliente, int(id_contrato)
        )
        if contexto_produto and contexto_produto.get("informativo"):
            if gerar_acordo:
                raise NenhumaDividaException(contexto_produto["mensagem"])
            return regra_cedente.montar_produto_informativo_proposta(
                contexto_produto, id_contrato
            ), id_cedente

        # Produtos que so aceitam acordo a vista nao podem ser parcelados
        # (plano > 1) nem reparcelados, salvo liberacao via IDT_20.
        if (
            contexto_produto
            and contexto_produto.get("somente_avista")
            and int(plano or 1) > 1
        ):
            raise NenhumaDividaException("Este produto permite apenas acordo à vista.")

        if contexto_produto:
            nm_produto = contexto_produto.get("produto") or nm_produto
        if id_cedente in CEDENTES_COM_PRODUTO and not nm_produto:
            nm_produto = consultar_produto_cedente(
                id_cedente,
                id_cliente,
                contrato.id_contrato,
                xml_divida,
            )
        nm_produto = regra_cedente.descrever_produto(xml_divida, nm_produto)
        contrato.atualizar_data(data_vencimento)
        cartao_35 = None
        if id_cedente in (65, 73):
            contrato.atualizar_valores(contrato.valor,0,0,plano)

        elif contrato.id_cedente in (81, 104):
            if NegociacaoDivida._condicao_informada(condicao) and plano != 1:
                raise NenhumaDividaException("Condicoes de pagamento somente para propostas a vista.")

            nm_produto = nm_produto or ConsultaContratoDetalhe(id_cliente, id_contrato).consultar_nm_produto()
            atraso = int(extrair_tag(xml_divida, "<Atraso>","</Atraso>"))
            if BancoBeta.eh_produto_cartao(nm_produto) and atraso <= 35 and gerar_acordo == False and plano == 1:
                cartao_35 = 'SIM'
                proposta_avista = ValoresDividas.proposta_avista_cartao_35(contrato)
                if not proposta_avista:
                    raise CollectSysException(mensagem="Nao foi possivel obter a proposta a vista original.")

                proposta = {
                    "origem": "COLLECTSYS",
                    "valorEntrada": proposta_avista["valorEntrada"],
                    "dataPagamento": proposta_avista["dataPagamento"].isoformat(),
                    "boleto": proposta_avista["boleto"],
                }
                detalhe_proposta = BancoBeta.detalhe_proposta(
                    nm_produto,
                    plano,
                    cartao_35,
                    condicao,
                )
                if detalhe_proposta:
                    proposta.update(detalhe_proposta)
                contrato_utilizado = {
                    "contrato": contrato.id_contrato,
                    "valorOriginal": round(contrato.valor, 2),
                    "valorAtualizado": round(_valor_atualizado_divida_xml(xml_divida), 2),
                }
                if nm_produto:
                    contrato_utilizado["produto"] = nm_produto
                if numero_contrato_banco:
                    contrato_utilizado["NumeroContratoBanco"] = numero_contrato_banco
                proposta["quantidadeContratos"] = 1
                proposta["contratosUtilizados"] = [contrato_utilizado]
                return proposta, id_cedente

            valor_entrada_consulta = (
                valor_entrada_informada
                if valor_entrada_informada is not None and valor_entrada_informada > 0
                else contrato.valor
            )
            calculo_parcelamento = Calcular(
                contrato.nome_cedente,
                contrato.id_cliente,
                contrato.id_cedente,
                plano,
                valor_entrada_consulta,
                contrato.xml,
                contrato.data_pagamento,
                condicao if contrato.id_cedente in (81, 104) else None
            )
            if BancoBeta.eh_produto_cartao(nm_produto) and atraso <= 35:
                cartao_35 = 'SIM'

            retorno_parcelamento = calculo_parcelamento.calcular_acordo_com_detalhes(
                parcelado="VALOR ENTRADA PD",
                cartao_35=cartao_35,
            )
            if not isinstance(retorno_parcelamento, tuple) or len(retorno_parcelamento) != 5:
                if BancoBeta.eh_erro_sem_propostas(str(retorno_parcelamento)):
                    raise NenhumaDividaException(BancoBeta.mensagem_sem_propostas())
                parcela_min_erro, parcela_max_erro = capturar_intervalo_parcelamento(str(retorno_parcelamento))
                if parcela_min_erro or parcela_max_erro:
                    raise NenhumaDividaException(
                        NegociacaoDivida._mensagem_plano_indisponivel(
                            parcela_min_erro,
                            parcela_max_erro,
                            " para parcelamento de cartao",
                        )
                    )
                if BancoBeta.eh_erro_sem_parcelamento(str(retorno_parcelamento)):
                    raise NenhumaDividaException(BancoBeta.mensagem_parcelamento_indisponivel())
                raise CollectSysException(mensagem=str(retorno_parcelamento))

            valor_min, valor_max, parcela_min, parcela_max, cartao_35 = retorno_parcelamento
            parcela_min = parcela_min or 1
            parcela_max = parcela_max or 1
            if parcela_max < parcela_min:
                parcela_max = parcela_min
            if plano != 1 and parcela_max <= 1:
                raise NenhumaDividaException("Apenas propostas a vista para esse contrato")
            if plano != 1 and (plano < parcela_min or plano > parcela_max):
                raise NenhumaDividaException(
                    NegociacaoDivida._mensagem_plano_indisponivel(
                        parcela_min,
                        parcela_max,
                        " para parcelamento de cartao",
                    )
                )
            valor_minimo_permitido = max(float(valor_min or 0), 50.0)
            valor_maximo_permitido = float(valor_max or 0)
            if valor_entrada_informada in (None, 0):
                valor_entrada_tratado = BancoBeta.valor_entrada(
                    contrato.xml,
                    plano,
                    valor_minimo_permitido,
                    valor_maximo_permitido,
                )
                if cartao_35 == 'SIM':
                    valor_entrada_tratado = valor_entrada_tratado + 10.0
                    if valor_maximo_permitido:
                        valor_entrada_tratado = min(valor_entrada_tratado, valor_maximo_permitido)
            else:
                valor_maximo_valido = (
                    valor_maximo_permitido
                    if valor_maximo_permitido >= valor_minimo_permitido
                    else 0
                )
                if (
                    valor_entrada_informada < valor_minimo_permitido
                    or (
                        plano == 1
                        and (
                            valor_maximo_valido > 0
                            and valor_entrada_informada > valor_maximo_valido
                        )
                    )
                ):
                    if valor_maximo_valido <= 0:
                        raise NenhumaDividaException(
                            f"Valor de entrada deve ser no minimo {str(round(valor_minimo_permitido, 2)).replace('.', ',')}"
                        )
                    raise NenhumaDividaException(
                        f"Valor de entrada deve ser entre {str(round(valor_minimo_permitido, 2)).replace('.', ',')} e {str(round(valor_maximo_valido, 2)).replace('.', ',')}"
                    )
                valor_entrada_tratado = valor_entrada_informada

            contrato.atualizar_valores(valor_entrada_tratado,0,0,plano)

        else:
            contrato.atualizar_valores(valor_entrada,0,0,plano)

        if contrato.id_cedente == 14:
            tipo_negociacao = tipo_negociacao_nu(
                condicao,
                maior_numero_prestacao,
                len(parcelas_em_atraso),
            )
        else:
            tipo_negociacao = regra_cedente.tipo_negociacao(
                condicao,
                maior_numero_prestacao,
                len(parcelas_em_atraso),
            )

        # Produto consignado sem liberacao de IDT_20 (somente a vista): a
        # proposta e apenas o pagamento das parcelas em atraso, nunca um
        # reparcelamento do contrato inteiro.
        delta_somente_avista = (
            contrato.id_cedente == 65
            and bool(contexto_produto)
            and contexto_produto.get("somente_avista")
        )
        if delta_somente_avista:
            tipo_negociacao = "parcelas em atraso"

        condicao_calculo = condicao if contrato.id_cedente in (14, 43, 65, 81, 104) else None
        if contrato.id_cedente == 14:
            if tipo_negociacao == "quitacao":
                condicao_calculo = None
            elif tipo_negociacao in ("parcelas em atraso", "todas em atraso"):
                condicao_calculo = len(parcelas_em_atraso) or None
        elif contrato.id_cedente == 65:
            if delta_somente_avista:
                # So as parcelas em atraso sao enviadas ao calculo.
                condicao_calculo = len(parcelas_em_atraso) or None
            else:
                # Por padrao o parcelamento renegocia o contrato inteiro (todas
                # as parcelas). O `condicao` e opcional e so filtra as N mais
                # atrasadas quando o cliente informa explicitamente.
                condicao_calculo = (
                    condicao if NegociacaoDivida._condicao_informada(condicao) else None
                )

        if contrato.id_cedente not in CEDENTES_CALCULO_DETALHE:
            resultado = Calcular(contrato.nome_cedente,contrato.id_cliente,contrato.id_cedente,
                                contrato.qtd_parcelas, contrato.valor, contrato.xml, contrato.data_pagamento, condicao_calculo).calcular_acordo()
        else:
            resultado = Calcular(contrato.nome_cedente,contrato.id_cliente,contrato.id_cedente,
                                contrato.qtd_parcelas, contrato.valor, contrato.xml, contrato.data_pagamento, condicao_calculo).calcular_acordo_com_detalhes(cartao_35=cartao_35)

        if id_cedente in (81, 104) and BancoBeta.eh_erro_sem_propostas(resultado):
            raise NenhumaDividaException(BancoBeta.mensagem_sem_propostas())

        if "<RetornoErro>" in resultado:
            if id_cedente in CEDENTES_BETA:
                erro_valor_entrada = NegociacaoDivida._erro_valor_entrada_beta(resultado)
                if erro_valor_entrada:
                    raise erro_valor_entrada

            if id_cedente in CEDENTES_PARCELAMENTO_MIN_MAX:
                parcela_min_erro, parcela_max_erro = capturar_intervalo_parcelamento(resultado)
                if parcela_min_erro or parcela_max_erro:
                    complemento = " para parcelamento de cartao" if id_cedente in CEDENTES_BETA else ""
                    raise NenhumaDividaException(
                        NegociacaoDivida._mensagem_plano_indisponivel(
                            parcela_min_erro,
                            parcela_max_erro,
                            complemento,
                        )
                    )
            if id_cedente in (81, 104) and BancoBeta.eh_erro_sem_parcelamento(resultado):
                raise NenhumaDividaException(BancoBeta.mensagem_parcelamento_indisponivel())
            if id_cedente in CEDENTES_TETA_COMUM and eh_erro_contrato_nao_encontrado(resultado):
                raise NenhumaDividaException(MENSAGEM_SEM_DIVIDA_ATIVA)
            if id_cedente in CEDENTES_TETA_COMUM and eh_erro_teta_nao_negociavel(resultado):
                raise NenhumaDividaException(MENSAGEM_NAO_NEGOCIAVEL)
            raise CollectSysException(mensagem=resultado)

        if id_cedente in CEDENTES_BETA:
            erro_valor_entrada = NegociacaoDivida._erro_valor_entrada_beta(resultado)
            if erro_valor_entrada:
                raise erro_valor_entrada

        if "falha ao calcular dívida" in resultado and id_cedente in (81, 104):
            raise CollectSysException(mensagem=resultado)

        if id_cedente in CEDENTES_TETA_COMUM and eh_erro_contrato_nao_encontrado(resultado):
            raise NenhumaDividaException(MENSAGEM_SEM_DIVIDA_ATIVA)
        if id_cedente in CEDENTES_TETA_COMUM and eh_erro_teta_nao_negociavel(resultado):
            raise NenhumaDividaException(MENSAGEM_NAO_NEGOCIAVEL)

        if id_cedente in CEDENTES_TETA_COMUM:
            parcela_min_erro, parcela_max_erro = capturar_intervalo_parcelamento(resultado)
            if parcela_min_erro or parcela_max_erro:
                raise NenhumaDividaException(
                    NegociacaoDivida._mensagem_plano_indisponivel(
                        parcela_min_erro,
                        parcela_max_erro,
                    )
                )

        if id_cedente in (81, 104) and BancoBeta.eh_erro_sem_parcelamento(resultado):
            raise NenhumaDividaException(BancoBeta.mensagem_parcelamento_indisponivel())

        if not regra_cedente.resultado_calculo_parcelas_valido(resultado, plano):
            if id_cedente == 43:
                parcelamento_maximo_valido = None
                teto_candidato = min(plano - 1, limite_max_parcelas or plano - 1)
                for plano_candidato in range(teto_candidato, 0, -1):
                    calculo_candidato = Calcular(
                        contrato.nome_cedente,
                        contrato.id_cliente,
                        contrato.id_cedente,
                        plano_candidato,
                        contrato.valor,
                        contrato.xml,
                        contrato.data_pagamento,
                        condicao_calculo,
                    )
                    if contrato.id_cedente not in CEDENTES_CALCULO_DETALHE:
                        resultado_candidato = calculo_candidato.calcular_acordo()
                    else:
                        resultado_candidato = calculo_candidato.calcular_acordo_com_detalhes(
                            cartao_35=cartao_35
                        )

                    if (
                        "<RetornoErro>" not in resultado_candidato
                        and regra_cedente.resultado_calculo_parcelas_valido(
                            resultado_candidato,
                            plano_candidato,
                        )
                    ):
                        parcelamento_maximo_valido = plano_candidato
                        break

                if parcelamento_maximo_valido is not None:
                    raise NenhumaDividaException(
                        regra_cedente.mensagem_parcelamento_maximo(
                            parcelamento_maximo_valido
                        )
                    )

            mensagem_calculo_invalido = regra_cedente.mensagem_resultado_calculo_invalido(
                resultado,
                plano,
            )
            raise NenhumaDividaException(
                mensagem_calculo_invalido or "O cálculo retornado não é válido para o plano solicitado."
            )

        if gerar_acordo == False:
            array_parcela = extrair_array(resultado, "<ParcelaAcordo>", "</ParcelaAcordo>")
            if not array_parcela:
                raise CollectSysException(mensagem=resultado)

            valor_parcela = extrair_tag(array_parcela, "<ValorParcela>", "</ValorParcela>")
            if not valor_parcela:
                raise CollectSysException(mensagem=resultado)

            valor = float(valor_parcela)
            if (
                id_cedente in (81, 104)
                and valor_entrada_informada not in (None, 0)
                and abs(valor - float(valor_entrada_informada)) > 0.01
            ):
                raise NenhumaDividaException(
                    f"Valor de entrada indisponivel. A simulacao retornou entrada de {str(round(valor, 2)).replace('.', ',')} para o valor solicitado de {str(round(float(valor_entrada_informada), 2)).replace('.', ',')}"
                )

            vencimento =  re.sub(r'T.*', '', extrair_tag(resultado,'<DataParcela>', '</DataParcela>'))

            proposta = {
                        "origem": "COLLECTSYS",
                        "valorEntrada":valor,
                        "dataPagamento":vencimento,
                    }

            if tipo_negociacao:
                proposta["tipoNegociacao"] = tipo_negociacao

            if plano > 1:
                resultado = resultado.replace(array_parcela, "")
                array_parcela = extrair_array(resultado, "<ParcelaAcordo>", "</ParcelaAcordo>")
                if not array_parcela:
                    raise CollectSysException(mensagem=resultado)

                valor_parcelas_tag = extrair_tag(array_parcela, "<ValorParcela>", "</ValorParcela>")
                if not valor_parcelas_tag:
                    raise CollectSysException(mensagem=resultado)

                valor_parcelas = float(valor_parcelas_tag)

                proposta.update({
                            "valorParcelas":valor_parcelas,
                            "quantidadeParcelas":plano,
                            "valorTotalAcordo": _valor_total_acordo(valor, valor_parcelas, plano)
                        })

            if id_cedente in (81, 104):
                detalhe_proposta = BancoBeta.detalhe_proposta(
                    nm_produto,
                    plano,
                    cartao_35,
                    condicao,
                )
                if detalhe_proposta:
                    proposta.update(detalhe_proposta)

            if nm_produto:
                proposta["produto"] = nm_produto

            if id_cedente in CEDENTES_TETA_COMUM and contratos_teta:
                if len(contratos_teta) > 1:
                    proposta.pop("contrato", None)
                proposta["quantidadeContratos"] = len(contratos_teta)
                proposta["contratosUtilizados"] = contratos_teta
            elif id_cedente in CEDENTES_COM_PRODUTO:
                contrato_utilizado = {
                    "contrato": contrato.id_contrato,
                    "valorOriginal": round(contrato.valor, 2),
                    "valorAtualizado": round(_valor_atualizado_divida_xml(xml_divida), 2),
                }
                if nm_produto:
                    contrato_utilizado["produto"] = nm_produto
                if numero_contrato_banco:
                    contrato_utilizado["NumeroContratoBanco"] = numero_contrato_banco
                proposta["quantidadeContratos"] = 1
                proposta["contratosUtilizados"] = [contrato_utilizado]

            return proposta, id_cedente
        else:
            xml_acordo = extrair_array(resultado, "<Acordo>", "</Acordo>")
            if id_cedente in (81, 104) and valor_entrada_informada not in (None, 0):
                array_parcela = extrair_array(xml_acordo or resultado, "<ParcelaAcordo>", "</ParcelaAcordo>")
                valor_parcela = extrair_tag(array_parcela or "", "<ValorParcela>", "</ValorParcela>")
                if valor_parcela and abs(float(valor_parcela) - float(valor_entrada_informada)) > 0.01:
                    raise NenhumaDividaException(
                        f"Valor de entrada indisponivel. A simulacao retornou entrada de {str(round(float(valor_parcela), 2)).replace('.', ',')} para o valor solicitado de {str(round(float(valor_entrada_informada), 2)).replace('.', ',')}"
                    )

            return xml_acordo, id_cedente
