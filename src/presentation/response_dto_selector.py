import os

from dotenv import load_dotenv

from src.domain.dtos.negociacao_response_dto import NegociacaoResponseDTO

load_dotenv()


def usar_contrato_novo() -> bool:
    valor = os.getenv("API_RESPONSE_V2", "true").strip().lower()
    if valor in {"1", "true", "yes", "sim", "on"}:
        return True
    if valor in {"0", "false", "no", "nao", "não", "off"}:
        return False
    raise ValueError("API_RESPONSE_V2 deve ser true ou false")


def obter_negociacao_response_dto():
    if usar_contrato_novo():
        return NegociacaoResponseDTO

    # Importacao intencionalmente tardia: ao aposentar o legado, este arquivo
    # pode ser apagado junto com API_RESPONSE_V2 sem afetar o contrato novo.
    from src.domain.dtos.negociacao_response_legacy_dto import (
        NegociacaoResponseLegacyDTO,
    )

    return NegociacaoResponseLegacyDTO
