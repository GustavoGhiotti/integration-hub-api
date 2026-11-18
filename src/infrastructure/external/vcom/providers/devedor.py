from urllib.parse import quote

from src.infrastructure.external.vcom.providers.client import VcomClient


class VcomDevedor:
    def __init__(self, client: VcomClient | None = None):
        self.client = client or VcomClient()

    def consultar_por_cpf(self, cpf_cnpj: str) -> dict | None:
        return self.client.get(f"/api/Devedor/{quote(str(cpf_cnpj), safe='')}")

