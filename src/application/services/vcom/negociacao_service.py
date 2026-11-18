from __future__ import annotations

import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextvars import copy_context
from datetime import date, datetime, timedelta
from decimal import Decimal

from src.application.services.vcom.credor_id import id_credor_externo, id_credor_vcom
from src.domain.exceptions.collectsys_exception import NenhumaDividaException, TabularException
from src.domain.utils.ajusta_telefone import ajusta_telefone
from src.infrastructure.external.vcom import VcomBoleto, VcomCalculo, VcomDevedor, VcomHistorico, VcomTitulo
from src.infrastructure.external.vcom.gateways.divida_ativa_vcom_gateway import VcomDividaAtivaGateway
from src.infrastructure.external.vcom.dto import (
    VcomCalculoParcelaRequest,
    VcomCalculoRequest,
    VcomCalculoTituloRequest,
    VcomHistoricoRequest,
    VcomOpcoesParcelamentoRequest,
)
from src.application.services.collectsys.meios_pagamentos_service import Boleto


CREDORES_UPSILON_VCOM = (2, 3)


class VcomNegociacaoService:
    @staticmethod
    async def dados_cliente(cpf_cnpj: str) -> dict:
        dados = VcomDevedor().consultar_por_cpf(cpf_cnpj)
        if not dados:
            return {"cpfCnpj": cpf_cnpj}

        nome_completo = str(dados.get("NOME_PES") or "").strip()
        nome = nome_completo.split()
        return {
            "nome": nome[0] if nome else "",
            "nomeCompleto": nome_completo,
            "cpfCnpj": cpf_cnpj,
        }

    @staticmethod
    async def obter_cedentes(cpf_cnpj: str) -> list[dict]:
        cedentes = await VcomDividaAtivaGateway().obter_por_cpf(cpf_cnpj)

        retorno = []
        for cedente in cedentes:
            item = {
                "origem": cedente.origem,
                "cedente": cedente.cedente,
                "idCedente": cedente.id_cedente,
                "idCliente": cedente.id_cliente,
                "possuiDividaAtiva": cedente.possui_divida_ativa,
            }
            if not cedente.possui_divida_ativa:
                item["mensagem"] = "Cliente localizado nesta carteira, mas nao possui divida ativa."
            if cedente.contratos:
                item["Contratos"] = [
                    {
                        "origem": cedente.origem,
                        "idContrato": contrato.id_contrato,
                        "grupo": contrato.grupo,
                    }
                    for contrato in cedente.contratos
                ]
            retorno.append(item)

        return retorno

    @staticmethod
    def _data_calculo(data_referencia=None) -> date:
        data_calculo = data_referencia or date.today() + timedelta(days=6)
        if isinstance(data_calculo, datetime):
            data_calculo = data_calculo.date()
        if isinstance(data_calculo, str):
            data_calculo = datetime.strptime(data_calculo.split("T", 1)[0], "%Y-%m-%d").date()
        return VcomNegociacaoService._proximo_dia_util(data_calculo)

    @staticmethod
    def _proximo_dia_util(data_calculo: date) -> date:
        while data_calculo.weekday() >= 5:
            data_calculo += timedelta(days=1)
        return data_calculo

    @staticmethod
    def _parcelas_abertas(titulo: dict) -> list[dict]:
        return VcomNegociacaoService._parcelas_por_status(titulo, {"ABERTO"})

    @staticmethod
    def _parcelas_visiveis(titulo: dict) -> list[dict]:
        return VcomNegociacaoService._parcelas_por_status(titulo, {"ABERTO", "DEVOLVIDO", "PARCELADO"})

    @staticmethod
    def _parcelas_por_status(titulo: dict, status_permitidos: set[str]) -> list[dict]:
        parcelas = []
        for parcela in titulo.get("PARCELAS") or []:
            if str(parcela.get("STATUS_PARC") or "").upper() not in status_permitidos:
                continue
            parcelas.append(
                {
                    "numero": int(parcela.get("NUMERO_PARC") or 0),
                    "vencimento": str(parcela.get("VCTO_PARC") or "").split("T", 1)[0],
                    "valor": float(parcela.get("VR_PARC") or 0),
                    "valorOriginal": float(parcela.get("VR_ORIG_PARC") or parcela.get("VR_PARC") or 0),
                    "codigoParcela": parcela.get("COD_PARC"),
                }
            )
        return parcelas

    @staticmethod
    def _produto_titulo(titulo: dict) -> str | None:
        for origem in [titulo.get("AUX") or {}, titulo]:
            produto = str(origem.get("NomeCartao") or origem.get("NOME_CARTAO") or "").strip()
            if produto:
                return produto

        for parcela in titulo.get("PARCELAS") or []:
            aux = parcela.get("AUX") or {}
            produto = str(aux.get("NomeCartao") or aux.get("NOME_CARTAO") or "").strip()
            if produto:
                return produto

        return None

    @staticmethod
    def _contrato_base(titulo: dict, parcelas: list[dict]) -> dict:
        valor_original = round(sum(parcela["valorOriginal"] for parcela in parcelas), 2)
        valor_atualizado = round(sum(parcela["valor"] for parcela in parcelas), 2)
        contrato_externo = str(titulo.get("CONTRATO_TIT") or "").strip()
        return {
            "origem": "VCOM",
            "contrato": contrato_externo,
            "grupo": titulo.get("NOME_CRED") or "VCOM",
            "produto": VcomNegociacaoService._produto_titulo(titulo),
            "valorAtualizado": valor_atualizado,
            "valorOriginal": {
                "valor": valor_original,
                "atrasadoDesde": parcelas[0]["vencimento"] if parcelas else None,
                "parcelasEmAtraso": [
                    {
                        "parcela": parcela["numero"],
                        "valor": parcela["valorOriginal"],
                        "vencimento": parcela["vencimento"],
                    }
                    for parcela in parcelas
                ],
                "quantidadeParcelasEmAtraso": len(parcelas),
                "quantidadeParcelas": int(titulo.get("PLANO_TIT") or len(parcelas)),
            },
            "propostaSemDesconto": {"valor": valor_original},
            "propostaAvista": {},
        }

    @staticmethod
    def _titulo_parcelado(titulo: dict) -> bool:
        valor = titulo.get("PARCELADO_TIT")
        if isinstance(valor, str):
            return valor.strip().lower() == "true"
        return bool(valor)

    @staticmethod
    def _marcar_acordo_ativo(contrato_item: dict) -> dict:
        contrato_item["mensagem"] = "Contrato ja possui acordo ativo na VCOM."
        return contrato_item

    @staticmethod
    def _contrato_acordo_ativo(titulo: dict) -> dict:
        parcelas_acordo = VcomNegociacaoService._parcelas_abertas(titulo)
        parcelas_base = parcelas_acordo or VcomNegociacaoService._parcelas_visiveis(titulo)
        contrato_item = VcomNegociacaoService._contrato_base(titulo, parcelas_base)
        contrato_item.pop("propostaAvista", None)
        contrato_item.pop("propostaSemDesconto", None)
        contrato_item.pop("valorOriginal", None)
        contrato_item["parcelasAcordo"] = [
            {
                "numero": parcela["numero"],
                "vencimento": parcela["vencimento"],
                "valor": parcela["valor"],
                "valorOriginal": parcela["valorOriginal"],
                "codigoParcela": parcela["codigoParcela"],
            }
            for parcela in parcelas_acordo
        ]
        contrato_item["acordo"] = {
            "ValorTotalAcordo": round(sum(parcela["valor"] for parcela in parcelas_acordo), 2),
            "quantidadeParcelas": len(parcelas_acordo),
            "primeiroVencimento": parcelas_acordo[0]["vencimento"] if parcelas_acordo else None,
            "ultimoVencimento": parcelas_acordo[-1]["vencimento"] if parcelas_acordo else None,
        }
        return VcomNegociacaoService._marcar_acordo_ativo(contrato_item)

    @staticmethod
    def _titulo_request(titulo: dict, permitir_visiveis: bool = False) -> VcomCalculoTituloRequest:
        parcelas = VcomNegociacaoService._parcelas_abertas(titulo)
        if not parcelas and permitir_visiveis:
            parcelas = VcomNegociacaoService._parcelas_visiveis(titulo)
        if not parcelas:
            raise NenhumaDividaException("Contrato sem parcelas em aberto na VCOM.")

        return VcomCalculoTituloRequest(
            contrato=str(titulo.get("CONTRATO_TIT") or "").strip(),
            parcelas=[
                VcomCalculoParcelaRequest(
                    numero=parcela["numero"],
                    vencimento=parcela["vencimento"],
                )
                for parcela in parcelas
            ],
        )

    @staticmethod
    def _eh_upsilon(id_credor_api: int | str | None) -> bool:
        if id_credor_api is None:
            return False
        return int(id_credor_api) in CREDORES_UPSILON_VCOM

    @staticmethod
    def _titulos_calculo(cpf_cnpj: str, titulo: dict, id_credor_api: int) -> list[dict]:
        if not VcomNegociacaoService._eh_upsilon(id_credor_api):
            return [titulo]

        titulos = [
            titulo_candidato
            for titulo_candidato in VcomNegociacaoService._titulos_candidatos(cpf_cnpj, titulo, id_credor_api)
            if VcomNegociacaoService._parcelas_abertas(titulo_candidato)
            or VcomNegociacaoService._parcelas_visiveis(titulo_candidato)
        ]
        return titulos or [titulo]

    @staticmethod
    def _titulos_request(titulos: list[dict], permitir_visiveis: bool = False) -> list[VcomCalculoTituloRequest]:
        return [
            VcomNegociacaoService._titulo_request(titulo, permitir_visiveis=permitir_visiveis)
            for titulo in titulos
        ]

    @staticmethod
    def _contratos_agrupados(titulos: list[dict]) -> list[dict]:
        return [
            {
                "contrato": str(titulo.get("CONTRATO_TIT") or "").strip(),
                "produto": VcomNegociacaoService._produto_titulo(titulo),
                "parcelasEmAtraso": [
                    {
                        "parcela": parcela["numero"],
                        "valor": parcela["valorOriginal"],
                        "vencimento": parcela["vencimento"],
                    }
                    for parcela in VcomNegociacaoService._parcelas_visiveis(titulo)
                ],
                "valorOriginal": round(
                    sum(parcela["valorOriginal"] for parcela in VcomNegociacaoService._parcelas_visiveis(titulo)),
                    2,
                ),
                "valorAtualizado": round(
                    sum(parcela["valor"] for parcela in VcomNegociacaoService._parcelas_visiveis(titulo)),
                    2,
                ),
            }
            for titulo in titulos
        ]

    @staticmethod
    def _contrato_agrupado_base(titulos: list[dict]) -> dict:
        parcelas = []
        contratos = []
        for titulo in titulos:
            contrato = str(titulo.get("CONTRATO_TIT") or "").strip()
            parcelas_titulo = VcomNegociacaoService._parcelas_visiveis(titulo)
            if contrato:
                contratos.append(contrato)
            parcelas.extend(parcelas_titulo)

        valor_original = round(sum(parcela["valorOriginal"] for parcela in parcelas), 2)
        valor_atualizado = round(sum(parcela["valor"] for parcela in parcelas), 2)
        primeiro_titulo = titulos[0]
        return {
            "propostaAvista": {},
            "propostaSemDesconto": {"valor": valor_original},
            "quantidadeContratos": len(titulos),
            "valorOriginal": {
                "valor": valor_original,
                "atrasadoDesde": min((parcela["vencimento"] for parcela in parcelas), default=None),
                "quantidadeParcelasEmAtraso": len(parcelas),
                "quantidadeParcelas": len(parcelas),
            },
            "valorAtualizado": valor_atualizado,
            "grupo": primeiro_titulo.get("NOME_CRED") or "VCOM",
            "origem": "VCOM",
            "contratosUtilizados": VcomNegociacaoService._contratos_agrupados(titulos),
        }

    @staticmethod
    def _opcoes_parcelamento(
        *,
        calculo: VcomCalculo,
        cpf_cnpj: str,
        id_credor_api: int,
        titulo: dict,
        data_calculo,
    ) -> dict:
        request = VcomOpcoesParcelamentoRequest(
            cpf_cnpj=cpf_cnpj,
            id_credor=id_credor_api,
            data_calculo=data_calculo,
            titulos=VcomNegociacaoService._titulos_request(
                VcomNegociacaoService._titulos_calculo(cpf_cnpj, titulo, id_credor_api),
                permitir_visiveis=VcomNegociacaoService._eh_upsilon(id_credor_api),
            ),
        )
        return calculo.opcoes_parcelamento(request) or {}

    @staticmethod
    def _opcao_parcelamento(opcoes: dict, quantidade: int) -> dict | None:
        for opcao in opcoes.get("OpcoesDeParcelamento") or []:
            if int(opcao.get("QuantidadeDeParcelas") or 0) == int(quantidade):
                return opcao
        return None

    @staticmethod
    def _opcao_a_vista(opcoes: dict) -> dict | None:
        for opcao in opcoes.get("OpcoesDeParcelamento") or []:
            descricao = str(opcao.get("DescricaoOpcao") or "").lower()
            quantidade = int(opcao.get("QuantidadeDeParcelas") or 0)
            if quantidade == 1 and "vista" in descricao and opcao.get("IdOpcao"):
                return opcao
        return None

    @staticmethod
    def _limitar_opcoes_parcelamento(opcoes: list[dict], limite: int = 4) -> list[dict]:
        opcoes_validas = [
            opcao
            for opcao in opcoes
            if int(opcao.get("QuantidadeDeParcelas") or 0) > 0 and opcao.get("IdOpcao")
        ]
        opcoes_ordenadas = sorted(opcoes_validas, key=lambda opcao: int(opcao.get("QuantidadeDeParcelas") or 0))
        if limite <= 1:
            return opcoes_ordenadas[:1]
        if len(opcoes_ordenadas) <= limite:
            return opcoes_ordenadas

        ultimo_indice = len(opcoes_ordenadas) - 1
        selecionadas = {
            round(posicao * ultimo_indice / (limite - 1))
            for posicao in range(limite)
        }
        return [opcoes_ordenadas[indice] for indice in sorted(selecionadas)]

    @staticmethod
    def _titulos_por_cpf(cpf_cnpj: str) -> list[dict]:
        retorno = VcomTitulo().consultar_por_cpf(cpf_cnpj)
        if isinstance(retorno, dict):
            return [retorno]
        return retorno or []

    @staticmethod
    def _titulos_por_cpf_contrato(cpf_cnpj: str, contrato: str) -> list[dict]:
        retorno = VcomTitulo().consultar_por_cpf_contrato(cpf_cnpj, contrato)
        if isinstance(retorno, dict):
            return [retorno]
        return retorno or []

    @staticmethod
    def _obter_titulo(cpf_cnpj: str, contrato: str | None = None, id_contrato: int | str | None = None) -> dict:
        if contrato:
            titulos_contrato = VcomNegociacaoService._titulos_por_cpf_contrato(cpf_cnpj, contrato)
            if len(titulos_contrato) == 1:
                return titulos_contrato[0]

            for titulo in titulos_contrato:
                contrato_titulo = str(titulo.get("CONTRATO_TIT") or "").strip()
                if contrato_titulo == str(contrato).strip():
                    return titulo

            if titulos_contrato:
                return titulos_contrato[0]

        titulos = VcomNegociacaoService._titulos_por_cpf(cpf_cnpj)
        return VcomNegociacaoService._encontrar_titulo(titulos, contrato, id_contrato)

    @staticmethod
    def _encontrar_titulo(titulos: list[dict], contrato: str | None = None, id_contrato: int | str | None = None) -> dict:
        for titulo in titulos:
            contrato_titulo = str(titulo.get("CONTRATO_TIT") or "").strip()
            if contrato and contrato_titulo == str(contrato).strip():
                return titulo
            if id_contrato and contrato_titulo == str(id_contrato).strip():
                return titulo
            if (
                id_contrato
                and str(id_contrato).isdigit()
                and int(titulo.get("COD_TIT") or 0) == int(id_contrato)
            ):
                return titulo

        raise NenhumaDividaException("Contrato VCOM nao localizado.")

    @staticmethod
    def _chave_titulo(titulo: dict) -> tuple[int, str]:
        return (
            int(titulo.get("COD_TIT") or 0),
            str(titulo.get("CONTRATO_TIT") or "").strip(),
        )

    @staticmethod
    def _titulos_candidatos(cpf_cnpj: str, titulo_preferencial: dict, id_credor_api: int) -> list[dict]:
        candidatos = [titulo_preferencial]
        chaves = {VcomNegociacaoService._chave_titulo(titulo_preferencial)}

        for titulo in VcomNegociacaoService._titulos_por_cpf(cpf_cnpj):
            if int(titulo.get("COD_CRED") or 0) != int(id_credor_api):
                continue

            chave = VcomNegociacaoService._chave_titulo(titulo)
            if chave in chaves:
                continue

            candidatos.append(titulo)
            chaves.add(chave)

        return candidatos

    @staticmethod
    def _credor_do_titulo(titulo: dict, id_credor: int | str | None = None) -> int:
        return int(titulo.get("COD_CRED") or 0)

    @staticmethod
    def _titulo_com_acordo_ativo(titulos: list[dict], id_credor_api: int | None = None) -> dict | None:
        for titulo in titulos:
            if id_credor_api and int(titulo.get("COD_CRED") or 0) != int(id_credor_api):
                continue
            if VcomNegociacaoService._titulo_parcelado(titulo):
                return titulo
        return None

    @staticmethod
    def _mensagem_erro_calculo(erro: Exception) -> str:
        response = getattr(erro, "response", None)
        if response is not None:
            try:
                detalhe = response.json().get("detail")
                if detalhe:
                    return str(detalhe)
            except ValueError:
                pass

        mensagem = str(erro)
        if "'NoneType' object has no attribute 'get'" in mensagem:
            return "Contrato nao pode ser negociado no momento."
        if "500 Server Error" in mensagem and "/api/Calculo" in mensagem:
            return "Nao foi possivel calcular proposta a vista na VCOM."
        return mensagem

    @staticmethod
    def _valor_simulado(simulacao: dict) -> float:
        if not simulacao:
            return 0
        parcelas = simulacao.get("ParcelasSimuladas") or []
        return round(sum(float(parcela.get("Valor") or 0) for parcela in parcelas), 2)

    @staticmethod
    def _valor_parcelas_resumo(valor_total: float, valor_entrada: float, demais: list[dict]) -> float:
        quantidade = len(demais)
        if quantidade <= 0:
            return 0
        restante = Decimal(str(valor_total or 0)) - Decimal(str(valor_entrada or 0))
        return round(float(restante / Decimal(quantidade)), 2)

    @staticmethod
    def _valor_entrada_simulada(simulacao: dict) -> float:
        if not simulacao:
            return 0
        parcelas = simulacao.get("ParcelasSimuladas") or []
        entrada = next((parcela for parcela in parcelas if parcela.get("Entrada")), None)
        primeira = entrada or (parcelas[0] if parcelas else {})
        return VcomNegociacaoService._arredondar_entrada(primeira.get("Valor") or 0)

    @staticmethod
    def _arredondar_entrada(valor) -> float:
        valor_decimal = Decimal(str(valor or 0))
        if valor_decimal <= 0:
            return 0

        multiplo = Decimal("5")
        base = (valor_decimal // multiplo) * multiplo
        resto = valor_decimal - base
        if resto <= Decimal("2.5"):
            return float(base)
        return float(base + multiplo)

    @staticmethod
    def _aplicar_valor_calculado(contrato_item: dict, simulacao: dict) -> float:
        valor_calculado = VcomNegociacaoService._valor_simulado(simulacao)
        if valor_calculado <= 0:
            return valor_calculado

        contrato_item["propostaSemDesconto"] = {"valor": valor_calculado}
        return valor_calculado

    @staticmethod
    def _primeiro_vencimento(simulacao: dict) -> str | None:
        if not simulacao:
            return None
        parcelas = simulacao.get("ParcelasSimuladas") or []
        if not parcelas:
            return None
        return str(parcelas[0].get("Vencimento") or "").split("T", 1)[0]

    @staticmethod
    def _montar_calculo(
        *,
        cpf_cnpj: str,
        id_credor: int,
        titulo: dict,
        data_pagamento,
        valor_entrada: float | None = 0,
        parcelamento: int = 0,
        parcelar: bool = False,
        id_opcao_parcelamento: str | None = None,
        id_campanha_calculo: str | None = None,
        percentual_desconto: float | None = None,
    ) -> VcomCalculoRequest:
        quantidade_parcelas = max(int(parcelamento or 1), 1) if parcelar else 0
        return VcomCalculoRequest(
            cpf_cnpj=cpf_cnpj,
            credor=id_credor,
            data_calculo=data_pagamento,
            parcelar=parcelar,
            quantidade_parcelas=quantidade_parcelas,
            percentual_desconto=percentual_desconto if percentual_desconto is not None else 100,
            percentual_entrada=None if valor_entrada is None else 0,
            valor_entrada=valor_entrada,
            id_opcao_parcelamento=id_opcao_parcelamento,
            id_campanha_calculo=id_campanha_calculo,
            titulos=VcomNegociacaoService._titulos_request(
                VcomNegociacaoService._titulos_calculo(cpf_cnpj, titulo, id_credor),
                permitir_visiveis=VcomNegociacaoService._eh_upsilon(id_credor),
            ),
        )

    @staticmethod
    def _quantidade_maxima_parcelas(titulo: dict) -> int:
        plano = int(titulo.get("PLANO_TIT") or 0)
        parcelas_abertas = len(VcomNegociacaoService._parcelas_abertas(titulo))
        return max(plano, parcelas_abertas, 1)

    @staticmethod
    def _montar_proposta_calculo(
        simulacao: dict,
        quantidade: int,
        data_calculo,
        opcao: dict | None = None,
        campanha: dict | None = None,
        parcelamento_max: int | None = None,
    ) -> dict:
        if not simulacao:
            raise NenhumaDividaException("Contrato nao pode ser negociado no momento.")
        parcelas = simulacao.get("ParcelasSimuladas") or []
        entrada = next((parcela for parcela in parcelas if parcela.get("Entrada")), None)
        demais = [parcela for parcela in parcelas if not parcela.get("Entrada")]
        if quantidade > 1 and entrada is None and parcelas:
            entrada = parcelas[0]
            demais = parcelas[1:]
        primeira = entrada or (parcelas[0] if parcelas else {})
        valor_entrada = float(((entrada or {}) if quantidade > 1 else primeira).get("Valor") or 0)
        valor_total = VcomNegociacaoService._valor_simulado(simulacao)
        valor_parcela = (
            VcomNegociacaoService._valor_parcelas_resumo(valor_total, valor_entrada, demais)
            if quantidade > 1
            else float(primeira.get("Valor") or 0)
        )

        proposta = {
            "valorEntrada": valor_entrada,
            "qtdParcelas": quantidade,
            "parcelamentoMax": int(parcelamento_max or quantidade),
            "valorTotalAcordo": valor_total,
            "dataPagamento": VcomNegociacaoService._primeiro_vencimento(simulacao) or data_calculo.isoformat(),
        }
        if quantidade > 1:
            proposta["valorParcelas"] = valor_parcela
        return proposta

    @staticmethod
    def _campanhas_calculo(
        *,
        calculo: VcomCalculo,
        cpf_cnpj: str,
        id_credor_api: int,
        titulo: dict,
        data_calculo,
    ) -> list[dict]:
        request = VcomOpcoesParcelamentoRequest(
            cpf_cnpj=cpf_cnpj,
            id_credor=id_credor_api,
            data_calculo=data_calculo,
            titulos=VcomNegociacaoService._titulos_request(
                VcomNegociacaoService._titulos_calculo(cpf_cnpj, titulo, id_credor_api),
                permitir_visiveis=VcomNegociacaoService._eh_upsilon(id_credor_api),
            ),
        )
        return calculo.recuperar_campanhas(request)

    @staticmethod
    def _iterar_opcoes_campanhas(campanhas: list[dict]) -> list[tuple[dict, dict]]:
        pares = []
        for campanha in campanhas or []:
            for opcao in campanha.get("OpcoesDeParcelamento") or []:
                pares.append((campanha, opcao))
        return pares

    @staticmethod
    def _opcao_campanha(
        campanhas: list[dict],
        quantidade: int | None = None,
        id_opcao: str | None = None,
        id_campanha: str | None = None,
    ) -> tuple[dict, dict] | None:
        id_opcao = str(id_opcao).strip() if id_opcao not in (None, "") else None
        id_campanha = str(id_campanha).strip() if id_campanha not in (None, "") else None
        for campanha, opcao in VcomNegociacaoService._iterar_opcoes_campanhas(campanhas):
            if id_campanha and str(campanha.get("IdCampanha") or "").strip() != id_campanha:
                continue
            if id_opcao and str(opcao.get("IdOpcao") or "").strip() != id_opcao:
                continue
            if quantidade is not None and not id_opcao:
                if int(opcao.get("QuantidadeDeParcelas") or 0) != int(quantidade):
                    continue
            return campanha, opcao
        return None

    @staticmethod
    def _simular_proposta_avista_titulo(
        *,
        calculo: VcomCalculo,
        cpf_cnpj: str,
        id_credor_api: int,
        titulo: dict,
        data_calculo,
    ) -> dict | None:
        try:
            request = VcomNegociacaoService._montar_calculo(
                cpf_cnpj=cpf_cnpj,
                id_credor=id_credor_api,
                titulo=titulo,
                data_pagamento=data_calculo,
                parcelar=False,
            )
            simulacao = calculo.simular(request)
            return VcomNegociacaoService._montar_proposta_calculo(simulacao, 1, data_calculo)
        except Exception:
            return None

    @staticmethod
    def _simular_propostas_titulo(
        *,
        calculo: VcomCalculo,
        cpf_cnpj: str,
        id_credor_api: int,
        titulo: dict,
        data_calculo,
    ) -> list[dict]:
        propostas = []
        try:
            campanhas = VcomNegociacaoService._campanhas_calculo(
                calculo=calculo,
                cpf_cnpj=cpf_cnpj,
                id_credor_api=id_credor_api,
                titulo=titulo,
                data_calculo=data_calculo,
            )
        except Exception:
            return propostas

        opcoes_campanhas = [
            (campanha, opcao)
            for campanha, opcao in VcomNegociacaoService._iterar_opcoes_campanhas(campanhas)
            if int(opcao.get("QuantidadeDeParcelas") or 0) > 0 and opcao.get("IdOpcao")
        ]
        opcoes_campanhas = sorted(
            opcoes_campanhas,
            key=lambda item: (
                str(item[0].get("IdCampanha") or ""),
                int(item[1].get("QuantidadeDeParcelas") or 0),
            ),
        )
        parcelamento_max = max(
            (int(opcao.get("QuantidadeDeParcelas") or 0) for _, opcao in opcoes_campanhas),
            default=1,
        )

        opcoes_selecionadas = VcomNegociacaoService._limitar_opcoes_parcelamento(
            [{**opcao, "_campanha": campanha} for campanha, opcao in opcoes_campanhas]
        )

        def simular_opcao(opcao_selecionada: dict) -> dict | None:
            try:
                opcao = dict(opcao_selecionada)
                campanha = opcao.pop("_campanha", {})
                quantidade = int(opcao.get("QuantidadeDeParcelas") or 0)
                if quantidade <= 0:
                    return None
                request = VcomNegociacaoService._montar_calculo(
                    cpf_cnpj=cpf_cnpj,
                    id_credor=id_credor_api,
                    titulo=titulo,
                    data_pagamento=data_calculo,
                    parcelamento=quantidade,
                    parcelar=True,
                    id_opcao_parcelamento=opcao.get("IdOpcao"),
                    id_campanha_calculo=campanha.get("IdCampanha"),
                )
                if quantidade > 1:
                    simulacao_previa = calculo.simular(request)
                    entrada_calculada = VcomNegociacaoService._valor_entrada_simulada(simulacao_previa)
                else:
                    entrada_calculada = 0
                if entrada_calculada > 0:
                    request = VcomNegociacaoService._montar_calculo(
                        cpf_cnpj=cpf_cnpj,
                        id_credor=id_credor_api,
                        titulo=titulo,
                        data_pagamento=data_calculo,
                        valor_entrada=entrada_calculada,
                        parcelamento=quantidade,
                        parcelar=True,
                        id_opcao_parcelamento=opcao.get("IdOpcao"),
                        id_campanha_calculo=campanha.get("IdCampanha"),
                    )
                simulacao = calculo.simular(request)
                proposta = VcomNegociacaoService._montar_proposta_calculo(
                    simulacao,
                    quantidade,
                    data_calculo,
                    opcao=opcao,
                    campanha=campanha,
                    parcelamento_max=parcelamento_max,
                )
                return proposta
            except Exception:
                return None

        with ThreadPoolExecutor(max_workers=min(len(opcoes_selecionadas), 4) or 1) as executor:
            futures = {
                executor.submit(copy_context().run, simular_opcao, opcao): indice
                for indice, opcao in enumerate(opcoes_selecionadas)
            }
            resultados = []
            for future in as_completed(futures):
                proposta = future.result()
                if proposta:
                    resultados.append((futures[future], proposta))

        propostas = [proposta for _, proposta in sorted(resultados, key=lambda item: item[0])]

        if propostas:
            return propostas

        proposta_avista = VcomNegociacaoService._simular_proposta_avista_titulo(
            calculo=calculo,
            cpf_cnpj=cpf_cnpj,
            id_credor_api=id_credor_api,
            titulo=titulo,
            data_calculo=data_calculo,
        )
        return [proposta_avista] if proposta_avista else []

    @staticmethod
    async def obter_dados_divida(cpf_cnpj: str, id_credor: int | None = None, data=None) -> list[dict]:
        titulos = VcomTitulo().consultar_por_cpf(cpf_cnpj)

        if not titulos:
            raise NenhumaDividaException("No momento, nao constam dividas ativas do cliente em nossa assessoria.")

        titulos_parcelados = [titulo for titulo in titulos if VcomNegociacaoService._titulo_parcelado(titulo)]
        if titulos_parcelados:
            titulos = titulos_parcelados

        itens_processamento = []
        data_calculo = VcomNegociacaoService._data_calculo(data)
        titulos_agrupados_processados: set[tuple[int, str]] = set()

        for titulo in titulos:
            id_credor_contrato = int(titulo.get("COD_CRED") or 0)
            chave_titulo = VcomNegociacaoService._chave_titulo(titulo)
            if chave_titulo in titulos_agrupados_processados:
                continue

            parcelas = VcomNegociacaoService._parcelas_visiveis(titulo)
            if not parcelas:
                continue

            titulos_calculo = VcomNegociacaoService._titulos_calculo(cpf_cnpj, titulo, id_credor_contrato)
            formato_upsilon = VcomNegociacaoService._eh_upsilon(id_credor_contrato)
            if formato_upsilon:
                contrato_item = VcomNegociacaoService._contrato_agrupado_base(titulos_calculo)
                titulos_agrupados_processados.update(
                    VcomNegociacaoService._chave_titulo(titulo_calculo)
                    for titulo_calculo in titulos_calculo
                )
            else:
                contrato_item = VcomNegociacaoService._contrato_base(titulo, parcelas)

            if VcomNegociacaoService._titulo_parcelado(titulo):
                itens_processamento.append((len(itens_processamento), titulo, id_credor_contrato, contrato_item, True))
                continue

            itens_processamento.append((len(itens_processamento), titulo, id_credor_contrato, contrato_item, False))

        def processar_item(item) -> tuple[int, dict]:
            indice, titulo, id_credor_contrato, contrato_item, acordo_ativo = item
            if acordo_ativo:
                return indice, VcomNegociacaoService._contrato_acordo_ativo(titulo)

            calculo = VcomCalculo()
            try:
                request = VcomNegociacaoService._montar_calculo(
                    cpf_cnpj=cpf_cnpj,
                    id_credor=id_credor_contrato,
                    titulo=titulo,
                    data_pagamento=data_calculo,
                    parcelar=False,
                )
                simulacao = calculo.simular(request)
                if not simulacao:
                    raise NenhumaDividaException("Contrato nao pode ser negociado no momento.")
                valor_calculado = VcomNegociacaoService._valor_simulado(simulacao)
                contrato_item["propostaAvista"] = {
                    "valor": valor_calculado,
                    "pagamento": VcomNegociacaoService._primeiro_vencimento(simulacao) or data_calculo.isoformat(),
                }
            except Exception as erro:
                mensagem = VcomNegociacaoService._mensagem_erro_calculo(erro)
                mensagem_normalizada = unicodedata.normalize("NFKD", mensagem).encode("ascii", "ignore").decode().lower()
                if "nao permite calculo a vista" in mensagem_normalizada:
                    mensagem = "Credor aceita somente recebimento parcelado na VCOM."
                contrato_item["propostaAvista"] = {"mensagem": mensagem}

            return indice, contrato_item

        resultados = []
        with ThreadPoolExecutor(max_workers=min(len(itens_processamento), 6) or 1) as executor:
            futures = [executor.submit(copy_context().run, processar_item, item) for item in itens_processamento]
            for future in as_completed(futures):
                resultados.append(future.result())

        return [contrato for _, contrato in sorted(resultados, key=lambda item: item[0])]

    @staticmethod
    async def negociacao_parcelado(
        cpf_cnpj: str,
        contrato: str | None,
        id_credor: int | None = None,
        id_contrato: int | str | None = None,
        data=None,
    ) -> dict:
        titulos = VcomNegociacaoService._titulos_por_cpf(cpf_cnpj)
        titulo = VcomNegociacaoService._encontrar_titulo(titulos, contrato, id_contrato)
        id_credor_api = VcomNegociacaoService._credor_do_titulo(titulo, id_credor)
        titulos_calculo = VcomNegociacaoService._titulos_calculo(cpf_cnpj, titulo, id_credor_api)
        data_calculo = VcomNegociacaoService._data_calculo(data)
        calculo = VcomCalculo()

        titulo_acordo = VcomNegociacaoService._titulo_com_acordo_ativo(titulos, id_credor_api)
        if titulo_acordo:
            return {
                "origem": "VCOM",
                "nomeCedente": titulo_acordo.get("NOME_CRED") or "VCOM",
                "idCliente": cpf_cnpj,
                "contrato": str(titulo_acordo.get("CONTRATO_TIT") or "").strip(),
                "mensagem": "Contrato ja possui acordo ativo na VCOM.",
                "propostas": "Contrato ja possui acordo ativo na VCOM.",
            }

        propostas = VcomNegociacaoService._simular_propostas_titulo(
            calculo=calculo,
            cpf_cnpj=cpf_cnpj,
            id_credor_api=id_credor_api,
            titulo=titulo,
            data_calculo=data_calculo,
        )

        retorno = {
            "origem": "VCOM",
            "nomeCedente": titulo.get("NOME_CRED") or "VCOM",
            "idCliente": cpf_cnpj,
            "contrato": str(titulo.get("CONTRATO_TIT") or "").strip(),
            "propostas": propostas or "Nao ha propostas parceladas no momento",
        }
        if len(titulos_calculo) > 1:
            retorno.pop("contrato", None)
            retorno["quantidadeContratos"] = len(titulos_calculo)
            retorno["contratosUtilizados"] = VcomNegociacaoService._contratos_agrupados(titulos_calculo)

        return retorno

    @staticmethod
    async def proposta_cliente(
        cpf_cnpj: str,
        contrato: str | None,
        id_credor: int | None,
        valor_entrada: float,
        plano: int,
        data_pagamento,
        gravar: bool = False,
        id_contrato: int | str | None = None,
        id_opcao_parcelamento: str | None = None,
        id_campanha_calculo: str | None = None,
    ) -> tuple[dict, int]:
        valor_entrada_informada = None if valor_entrada is None else float(valor_entrada or 0)
        valor_entrada_vcom = valor_entrada_informada if valor_entrada_informada and valor_entrada_informada > 0 else None
        titulo = VcomNegociacaoService._obter_titulo(cpf_cnpj, contrato, id_contrato)
        id_credor_api = VcomNegociacaoService._credor_do_titulo(titulo, id_credor)
        titulos_calculo = VcomNegociacaoService._titulos_calculo(cpf_cnpj, titulo, id_credor_api)
        data_calculo = VcomNegociacaoService._data_calculo(data_pagamento)
        calculo = VcomCalculo()
        id_opcao_escolhida = id_opcao_parcelamento
        id_campanha_escolhida = id_campanha_calculo
        parcelar = plano > 1
        plano_calculo = max(int(plano or 1), 1)
        campanhas = []
        try:
            campanhas = VcomNegociacaoService._campanhas_calculo(
                calculo=calculo,
                cpf_cnpj=cpf_cnpj,
                id_credor_api=id_credor_api,
                titulo=titulo,
                data_calculo=data_calculo,
            )
        except Exception:
            campanhas = []

        if plano > 1 or id_opcao_escolhida or id_campanha_escolhida:
            opcao_campanha = VcomNegociacaoService._opcao_campanha(
                campanhas,
                quantidade=plano if plano > 1 else None,
                id_opcao=id_opcao_escolhida,
                id_campanha=id_campanha_escolhida,
            )
            opcao = opcao_campanha[1] if opcao_campanha else None
            campanha = opcao_campanha[0] if opcao_campanha else None
            if not opcao:
                raise NenhumaDividaException("Opcao de parcelamento nao disponivel na VCOM.")
            id_opcao_escolhida = opcao.get("IdOpcao")
            id_campanha_escolhida = campanha.get("IdCampanha") if campanha else id_campanha_escolhida
            plano_calculo = int(opcao.get("QuantidadeDeParcelas") or plano_calculo)
            parcelar = True
        else:
            opcao_campanha = VcomNegociacaoService._opcao_campanha(campanhas, quantidade=1)
            opcao = opcao_campanha[1] if opcao_campanha else None
            campanha = opcao_campanha[0] if opcao_campanha else None
            if opcao:
                id_opcao_escolhida = opcao.get("IdOpcao")
                id_campanha_escolhida = campanha.get("IdCampanha") if campanha else None
                plano_calculo = int(opcao.get("QuantidadeDeParcelas") or 1)
                parcelar = True

        request = VcomNegociacaoService._montar_calculo(
            cpf_cnpj=cpf_cnpj,
            id_credor=id_credor_api,
            titulo=titulo,
            data_pagamento=data_calculo,
            valor_entrada=valor_entrada_vcom,
            parcelamento=plano_calculo,
            parcelar=parcelar,
            id_opcao_parcelamento=id_opcao_escolhida,
            id_campanha_calculo=id_campanha_escolhida,
        )
        try:
            if plano_calculo > 1 and valor_entrada_vcom is None:
                simulacao_previa = calculo.simular(request)
                entrada_calculada = VcomNegociacaoService._valor_entrada_simulada(simulacao_previa)
                if entrada_calculada > 0:
                    valor_entrada_vcom = entrada_calculada
                    request = VcomNegociacaoService._montar_calculo(
                        cpf_cnpj=cpf_cnpj,
                        id_credor=id_credor_api,
                        titulo=titulo,
                        data_pagamento=data_calculo,
                        valor_entrada=valor_entrada_vcom,
                        parcelamento=plano_calculo,
                        parcelar=parcelar,
                        id_opcao_parcelamento=id_opcao_escolhida,
                        id_campanha_calculo=id_campanha_escolhida,
                    )
            simulacao = calculo.gravar(request) if gravar else calculo.simular(request)
            if not simulacao:
                raise NenhumaDividaException("Contrato nao pode ser negociado no momento.")
        except Exception as erro:
            mensagem = VcomNegociacaoService._mensagem_erro_calculo(erro)
            mensagem_normalizada = unicodedata.normalize("NFKD", mensagem).encode("ascii", "ignore").decode().lower()
            if plano_calculo != 1 or id_opcao_escolhida or "nao permite calculo a vista" not in mensagem_normalizada:
                raise NenhumaDividaException(mensagem)

            request = VcomNegociacaoService._montar_calculo(
                cpf_cnpj=cpf_cnpj,
                id_credor=id_credor_api,
                titulo=titulo,
                data_pagamento=data_calculo,
                valor_entrada=valor_entrada_vcom,
                parcelamento=1,
                parcelar=True,
                id_opcao_parcelamento="1",
                id_campanha_calculo=id_campanha_escolhida,
            )
            try:
                simulacao = calculo.gravar(request) if gravar else calculo.simular(request)
            except Exception as erro_fallback:
                raise NenhumaDividaException(VcomNegociacaoService._mensagem_erro_calculo(erro_fallback)) from erro_fallback
        parcelas = simulacao.get("ParcelasSimuladas") or []
        demais = [p for p in parcelas if not p.get("Entrada")]
        entrada = next((p for p in parcelas if p.get("Entrada")), None)
        if plano_calculo > 1 and entrada is None and parcelas:
            entrada = parcelas[0]
            demais = parcelas[1:]

        proposta = {
            "origem": "VCOM",
            "valorEntrada": float((entrada or parcelas[0] if parcelas else {}).get("Valor") or 0),
            "dataPagamento": VcomNegociacaoService._primeiro_vencimento(simulacao),
        }
        if gravar:
            proposta["codigoCalculo"] = simulacao.get("Id")
        if plano_calculo > 1:
            valor_total = VcomNegociacaoService._valor_simulado(simulacao)
            valor_entrada_retorno = float((entrada or {}).get("Valor") or valor_entrada_vcom or 0)
            proposta["valorEntrada"] = valor_entrada_retorno
            proposta["valorParcelas"] = VcomNegociacaoService._valor_parcelas_resumo(
                valor_total,
                valor_entrada_retorno,
                demais,
            )
            proposta["quantidadeParcelas"] = plano_calculo
            proposta["valorTotalAcordo"] = valor_total
        if id_opcao_escolhida:
            proposta["idOpcaoParcelamento"] = id_opcao_escolhida
        if id_campanha_escolhida:
            proposta["idCampanhaCalculo"] = id_campanha_escolhida
        proposta["quantidadeContratos"] = len(titulos_calculo)
        proposta["contratosUtilizados"] = VcomNegociacaoService._contratos_agrupados(titulos_calculo)
        return proposta, id_credor_externo(id_credor_api)

    @staticmethod
    def emitir_boleto(codigo_calculo: int, codigo_boleto: int = 0) -> dict:
        boleto_emitido = VcomBoleto().emitir(codigo_calculo, codigo_boleto)
        boleto_id = int(boleto_emitido.get("BoletoEmitidoId") or 0)
        retorno = {
            "boletoEmitidoId": boleto_id,
            "linhaDigitavel": boleto_emitido.get("LinhaDigitavel"),
            "codigoBarras": boleto_emitido.get("CodigoDeBarras"),
            "valor": boleto_emitido.get("Valor"),
            "vencimento": boleto_emitido.get("Vencimento"),
            "statusBoleto": boleto_emitido.get("StatusBoleto"),
            "statusRegistro": boleto_emitido.get("StatusRegistro"),
            "mensagem": "Boleto emitido com sucesso.",
        }
        if boleto_id:
            impresso = VcomBoleto().imprimir(boleto_id)
            arquivo = (impresso or {}).get("Arquivo")
            if arquivo:
                nome_boleto = f"boleto_vcom_{boleto_id}.pdf"
                retorno.update(Boleto._registrar_boleto(nome_boleto, arquivo, retorno["linhaDigitavel"], sobrescrever=True))
        return retorno

    @staticmethod
    def _valor_historico(valor) -> float:
        if valor in (None, ""):
            return 0
        if isinstance(valor, str):
            valor = valor.strip().replace(".", "").replace(",", ".") if "," in valor else valor.strip()
        return float(valor or 0)

    @staticmethod
    def tabular(
        cpf_cnpj: str,
        id_credor: int,
        id_acao: int,
        descricao: str,
        telefone: str,
        contrato: str | None = None,
        data=None,
        data_agendamento=None,
        valor: float | None = 0,
    ):
        id_credor_api = id_credor_vcom(id_credor)
        if id_credor_api is None:
            raise NenhumaDividaException("Credor VCOM nao informado para tabulacao.")
        ddd, numero = ajusta_telefone(telefone)
        data_requisicao = datetime.now()
        try:
            VcomHistorico().inserir_devedor(
                VcomHistoricoRequest(
                    cpf=cpf_cnpj,
                    codigo_ocorrencia=id_acao,
                    credor=id_credor_api,
                    complemento=descricao,
                    numero_contrato=contrato,
                    data=data or data_requisicao,
                    data_agendamento=data_agendamento or data or data_requisicao,
                    valor=VcomNegociacaoService._valor_historico(valor),
                    ddd=str(ddd),
                    telefone=str(numero),
                )
            )
        except Exception as erro:
            raise TabularException(VcomNegociacaoService._mensagem_erro_calculo(erro)) from erro
        return "Tabulado com Sucesso"
