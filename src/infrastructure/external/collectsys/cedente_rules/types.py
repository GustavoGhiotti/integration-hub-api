from __future__ import annotations

from dataclasses import dataclass
import unicodedata
from typing import Any


@dataclass
class AcordoDetalhe:
    nome: str
    valor: Any
    id_detalhe: int
    tipo_detalhe: str = "Acordo"
    origem: str = "Manual"


@dataclass
class RuleDecision:
    acao: str
    valor: Any = None

    @classmethod
    def recalcular(cls) -> "RuleDecision":
        return cls("recalcular")

    @classmethod
    def retornar(cls, valor: Any) -> "RuleDecision":
        return cls("retornar", valor)


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    without_accents = "".join(char for char in normalized if not unicodedata.combining(char))
    return without_accents.lower()
