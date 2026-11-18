from urllib.parse import quote

from src.infrastructure.external.vcom.providers.client import VcomClient


class VcomTitulo:
    def __init__(self, client: VcomClient | None = None):
        self.client = client or VcomClient()

    def consultar_por_cpf(self, cpf_cnpj: str) -> list[dict]:
        retorno = self.client.get(f"/api/Titulo/{quote(str(cpf_cnpj), safe='')}")
        return retorno or []

    def consultar_por_cpf_contrato(self, cpf_cnpj: str, contrato: str) -> dict | None:
        return self.client.get(
            f"/api/Titulo/{quote(str(cpf_cnpj), safe='')}/{quote(str(contrato).strip(), safe='')}"
        )

