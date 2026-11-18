from dataclasses import dataclass
from datetime import date, datetime


def _datetime_to_iso(value: date | datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time()).isoformat()
    return str(value)


@dataclass(slots=True)
class VcomHistoricoRequest:
    cpf: str
    codigo_ocorrencia: int
    credor: int
    complemento: str | None = None
    numero_contrato: str | None = None
    data: date | datetime | str | None = None
    data_agendamento: date | datetime | str | None = None
    valor: float | None = 0
    ddd: str | None = None
    telefone: str | None = None

    def to_dict(self) -> dict:
        payload = {
            "NumeroDeContrato": self.numero_contrato,
            "CodigoDaOcorrencia": self.codigo_ocorrencia,
            "Cpf": self.cpf,
            "Complemento": self.complemento,
            "Data": _datetime_to_iso(self.data),
            "DataDoAgendamento": _datetime_to_iso(self.data_agendamento),
            "Credor": self.credor,
            "Valor": self.valor,
            "Telefone": {
                "DDD": self.ddd,
                "Numero": self.telefone,
            },
        }
        return {key: value for key, value in payload.items() if value is not None}

