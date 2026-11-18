from src.infrastructure.external.vcom.dto import VcomCalculoRequest, VcomOpcoesParcelamentoRequest
from src.infrastructure.external.vcom.providers.client import VcomClient


class VcomCalculo:
    def __init__(self, client: VcomClient | None = None):
        self.client = client or VcomClient()

    def simular(self, request: VcomCalculoRequest) -> dict:
        return self.client.post("/api/Calculo", json=request.to_dict())

    def gravar(self, request: VcomCalculoRequest) -> dict:
        return self.client.put("/api/Calculo", json=request.to_dict())

    def opcoes_parcelamento(self, request: VcomOpcoesParcelamentoRequest) -> dict | None:
        return self.client.post("/api/Calculo/opcoes-parcelamento", json=request.to_dict())

    def recuperar_campanhas(self, request: VcomOpcoesParcelamentoRequest) -> list[dict]:
        retorno = self.client.post("/api/Calculo/recuperar-campanhas", json=request.to_dict())
        if isinstance(retorno, dict):
            return [retorno]
        return retorno or []

