from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def _metodo_negociacao(quantidade_contratos) -> str:
    try:
        return "AGRUPADO" if int(quantidade_contratos or 0) > 1 else "INDIVIDUAL"
    except (TypeError, ValueError):
        return "INDIVIDUAL"


def _clean(valor):
    if isinstance(valor, list):
        return [_clean(item) for item in valor]
    if isinstance(valor, dict):
        return {
            chave: _clean(item)
            for chave, item in valor.items()
            if chave != "origem" and item is not None
        }
    return valor


def _ordered_dict(raw: dict, ordem: list[str]) -> dict:
    retorno = {campo: raw[campo] for campo in ordem if campo in raw}
    for campo, valor in raw.items():
        if campo not in retorno:
            retorno[campo] = valor
    return _clean(retorno)


def _parcelas_por_contrato(parcelas_em_atraso):
    if not isinstance(parcelas_em_atraso, list):
        return {}, [] if parcelas_em_atraso is None else [parcelas_em_atraso]

    parcelas_por_contrato = {}
    parcelas_sem_contrato = []
    for item in parcelas_em_atraso:
        if isinstance(item, dict) and "contrato" in item:
            contrato = item.get("contrato")
            parcelas_por_contrato[str(contrato)] = (
                item.get("parcelasEmAtraso")
                or item.get("parcelas")
                or []
            )
        else:
            parcelas_sem_contrato.append(item)

    return parcelas_por_contrato, parcelas_sem_contrato


@dataclass(slots=True)
class ContratoUtilizadoDTO:
    contrato: Any = None
    parcelasEmAtraso: Any = None
    produto: str | None = None
    valorOriginal: float | int | None = None
    valorAtualizado: float | int | None = None
    NumeroContratoBanco: str | None = None

    @classmethod
    def from_raw(
        cls,
        contrato_item: dict,
        origem_item: dict | None = None,
        parcelas_por_contrato: dict | None = None,
        parcelas_sem_contrato: list | None = None,
    ) -> "ContratoUtilizadoDTO":
        origem_item = origem_item or {}
        parcelas_por_contrato = parcelas_por_contrato or {}
        parcelas_sem_contrato = parcelas_sem_contrato or []

        contrato = contrato_item.get("contrato") or origem_item.get("contrato")
        parcelas = contrato_item.get("parcelasEmAtraso")
        if parcelas is None and contrato is not None:
            parcelas = parcelas_por_contrato.get(str(contrato))
        if parcelas is None and parcelas_sem_contrato:
            parcelas = parcelas_sem_contrato

        valor_original = contrato_item.get("valorOriginal")
        if valor_original is None:
            valor_original = (origem_item.get("valorOriginal") or {}).get("valor")
        valor_atualizado = contrato_item.get("valorAtualizado")
        if valor_atualizado is None:
            valor_atualizado = origem_item.get("valorAtualizado")

        return cls(
            contrato=contrato,
            parcelasEmAtraso=parcelas,
            produto=contrato_item.get("produto") or origem_item.get("produto"),
            valorOriginal=valor_original,
            valorAtualizado=valor_atualizado,
            NumeroContratoBanco=contrato_item.get("NumeroContratoBanco")
            or origem_item.get("NumeroContratoBanco"),
        )

    def to_dict(self) -> dict:
        return _clean(asdict(self))


@dataclass(slots=True)
class VerificaContratoDTO:
    propostaAvista: dict = field(default_factory=dict)
    propostaSemDesconto: dict = field(default_factory=dict)
    valorOriginal: dict = field(default_factory=dict)
    quantidadeContratos: int = 1
    grupo: str | None = None
    metodoNegociacao: str = "INDIVIDUAL"
    contratosUtilizados: list[dict] = field(default_factory=list)
    parcelas: list[dict] | None = None

    @classmethod
    def from_raw(cls, item: dict) -> "VerificaContratoDTO":
        valor_original = dict(item.get("valorOriginal") or {})
        parcelas_por_contrato, parcelas_sem_contrato = _parcelas_por_contrato(
            valor_original.pop("parcelasEmAtraso", None)
        )

        contratos_origem = item.get("contratosUtilizados")
        if not contratos_origem and item.get("contrato") is not None:
            contratos_origem = [{"contrato": item.get("contrato")}]

        contratos_utilizados = [
            ContratoUtilizadoDTO.from_raw(
                contrato_item,
                item,
                parcelas_por_contrato,
                parcelas_sem_contrato,
            ).to_dict()
            for contrato_item in contratos_origem or []
        ]
        quantidade = item.get("quantidadeContratos") or len(contratos_utilizados) or 1

        return cls(
            propostaAvista=item.get("propostaAvista") or {},
            propostaSemDesconto=item.get("propostaSemDesconto") or {},
            valorOriginal=valor_original,
            quantidadeContratos=quantidade,
            grupo=item.get("grupo"),
            metodoNegociacao=_metodo_negociacao(quantidade),
            contratosUtilizados=contratos_utilizados,
            parcelas=item.get("parcelas") if "parcelas" in item else None,
        )

    def to_dict(self) -> dict:
        return _clean(asdict(self))


@dataclass(slots=True)
class InformacoesAcordoDTO:
    idCliente: Any = None
    vencimentoPagamento: str | None = None
    valorEntrada: float | None = None
    valorParcelas: float | None = None
    quantidadeParcelas: int | None = None
    valorTotalAcordo: float | None = None
    tipoNegociacao: str | None = None
    detalhe: str | None = None
    tipoProposta: str | None = None
    quantidadeContratos: int = 1
    metodoNegociacao: str = "INDIVIDUAL"
    contratosUtilizados: list[dict] = field(default_factory=list)

    @classmethod
    def from_proposta(cls, id_cliente, proposta: dict) -> "InformacoesAcordoDTO":
        proposta = NegociacaoResponseDTO.normalizar_proposta(proposta or {})
        contratos_utilizados = proposta.get("contratosUtilizados") or []
        if not contratos_utilizados and proposta.get("contrato") is not None:
            contratos_utilizados = [{"contrato": proposta.get("contrato")}]

        quantidade = (
            proposta.get("quantidadeContratos")
            or len(contratos_utilizados)
            or 1
        )

        return cls(
            idCliente=id_cliente,
            vencimentoPagamento=proposta.get("dataPagamento"),
            valorEntrada=proposta.get("valorEntrada"),
            valorParcelas=proposta.get("valorParcelas"),
            quantidadeParcelas=proposta.get("quantidadeParcelas"),
            valorTotalAcordo=proposta.get("valorTotalAcordo"),
            tipoNegociacao=proposta.get("tipoNegociacao"),
            detalhe=proposta.get("detalhe"),
            tipoProposta=proposta.get("tipoProposta"),
            quantidadeContratos=quantidade,
            metodoNegociacao=_metodo_negociacao(quantidade),
            contratosUtilizados=contratos_utilizados,
        )

    def to_dict(self) -> dict:
        return _clean(asdict(self))


class NegociacaoResponseDTO:
    INCLUI_INFORMACOES_ACORDO = True

    @staticmethod
    def remover_origem(retorno):
        return _clean(retorno)

    @staticmethod
    def metodo_negociacao(quantidade_contratos) -> str:
        return _metodo_negociacao(quantidade_contratos)

    @staticmethod
    def normalizar_verifica(contratos):
        if isinstance(contratos, dict):
            if "mensagem" in contratos or "erro" in contratos:
                return _clean(contratos)
            contratos = list(contratos.values())
        if not isinstance(contratos, list):
            return contratos

        retorno = []
        for item in contratos:
            if not isinstance(item, dict):
                retorno.append(_clean(item))
                continue
            retorno.append(VerificaContratoDTO.from_raw(item).to_dict())
        return retorno

    @staticmethod
    def aplicar_metodo_negociacao(retorno):
        if not isinstance(retorno, dict):
            return retorno

        quantidade = (
            retorno.get("quantidadeContratos")
            or len(retorno.get("contratosUtilizados") or [])
            or 1
        )
        retorno = dict(retorno)
        retorno["quantidadeContratos"] = quantidade
        retorno["metodoNegociacao"] = _metodo_negociacao(quantidade)
        return _clean(retorno)

    @staticmethod
    def normalizar_parcelamento(retorno):
        retorno = NegociacaoResponseDTO.aplicar_metodo_negociacao(retorno)
        if not isinstance(retorno, dict):
            return retorno

        return _ordered_dict(
            retorno,
            [
                "propostas",
                "nomeCedente",
                "idCliente",
                "contrato",
                "produto",
                "quantidadeContratos",
                "metodoNegociacao",
                "contratosUtilizados",
            ],
        )

    @staticmethod
    def normalizar_proposta(retorno, id_cedente=None):
        retorno = NegociacaoResponseDTO.aplicar_metodo_negociacao(retorno)
        if not isinstance(retorno, dict):
            return retorno

        return _ordered_dict(
            retorno,
            [
                "valorEntrada",
                "mensagem",
                "dataPagamento",
                "tipoNegociacao",
                "valorParcelas",
                "quantidadeParcelas",
                "valorTotalAcordo",
                "detalhe",
                "tipoProposta",
                "boleto",
                "codigoCalculo",
                "contrato",
                "produto",
                "quantidadeContratos",
                "metodoNegociacao",
                "contratosUtilizados",
            ],
        )

    @staticmethod
    def normalizar_informacoes_acordo(id_cliente, proposta):
        return InformacoesAcordoDTO.from_proposta(id_cliente, proposta or {}).to_dict()
