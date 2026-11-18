from src.infrastructure.external.vcom.dto import VcomHistoricoRequest
from src.infrastructure.external.vcom.providers.client import VcomClient


class VcomHistorico:
    def __init__(self, client: VcomClient | None = None):
        self.client = client or VcomClient()

    def inserir_devedor(self, request: VcomHistoricoRequest):
        return self.client.post("/api/Historico/devedor", json=request.to_dict(), return_none_on_404=False)

