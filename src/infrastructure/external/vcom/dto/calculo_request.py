from dataclasses import dataclass, field
from datetime import date, datetime


def _date_to_iso(value: date | datetime | str) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value).split("T", 1)[0]


@dataclass(slots=True)
class VcomCalculoParcelaRequest:
    numero: int
    vencimento: date | datetime | str

    def to_dict(self) -> dict:
        return {
            "Numero": self.numero,
            "Vencimento": _date_to_iso(self.vencimento),
        }


@dataclass(slots=True)
class VcomCalculoTituloRequest:
    contrato: str
    parcelas: list[VcomCalculoParcelaRequest]

    def to_dict(self) -> dict:
        return {
            "Contrato": self.contrato.strip(),
            "Parcelas": [parcela.to_dict() for parcela in self.parcelas],
        }


@dataclass(slots=True)
class VcomCalculoRequest:
    cpf_cnpj: str
    credor: int
    data_calculo: date | datetime | str
    titulos: list[VcomCalculoTituloRequest]
    parcelar: bool = False
    percentual_desconto: float | None = 50
    percentual_entrada: float | None = 0
    quantidade_parcelas: int = 0
    taxa_personalizada: bool | None = False
    tipo_taxa_personalizada: str | None = None
    valor_taxa_personalizada: float | None = 0
    valor_desconto: float | None = 0
    valor_entrada: float | None = 0
    id_opcao_parcelamento: str | None = None
    id_campanha_calculo: str | None = None

    def to_dict(self) -> dict:
        payload = {
            "CpfCnpj": self.cpf_cnpj,
            "Credor": self.credor,
            "DataCalculo": _date_to_iso(self.data_calculo),
            "Parcelar": self.parcelar,
            "PercentualDesconto": self.percentual_desconto,
            "PercentualEntrada": self.percentual_entrada,
            "QuantidadeParcelas": self.quantidade_parcelas,
            "TaxaPersonalizada": self.taxa_personalizada,
            "TipoDeTaxaPersonalizada": self.tipo_taxa_personalizada,
            "Titulos": [titulo.to_dict() for titulo in self.titulos],
            "ValorDeTaxaPersonalizada": self.valor_taxa_personalizada,
            "ValorDesconto": self.valor_desconto,
            "ValorEntrada": self.valor_entrada,
            "IdOpcaoParcelamento": self.id_opcao_parcelamento,
            "IdCampanhaCalculo": self.id_campanha_calculo,
        }
        if self.valor_entrada is None:
            payload.pop("ValorEntrada", None)
        if self.percentual_entrada is None:
            payload.pop("PercentualEntrada", None)
        return payload


@dataclass(slots=True)
class VcomOpcoesParcelamentoRequest:
    cpf_cnpj: str
    id_credor: int
    data_calculo: date | datetime | str
    titulos: list[VcomCalculoTituloRequest] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "CpfCnpj": self.cpf_cnpj,
            "DataCalculo": _date_to_iso(self.data_calculo),
            "IdCredor": self.id_credor,
            "Titulos": [titulo.to_dict() for titulo in self.titulos],
        }

