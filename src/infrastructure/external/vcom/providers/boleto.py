from src.infrastructure.external.vcom.providers.client import VcomClient


class VcomBoleto:
    def __init__(self, client: VcomClient | None = None):
        self.client = client or VcomClient()

    def emitir(self, codigo_calculo: int, codigo_boleto: int = 0) -> dict:
        return self.client.post(
            "/api/Boleto/emitir",
            json={
                "CodigoCalculo": codigo_calculo,
                "CodigoBoleto": codigo_boleto,
            },
        )

    def imprimir(self, boleto_emitido_id: int) -> dict | None:
        return self.client.get(f"/api/Boleto/imprimir/{boleto_emitido_id}")

    def consultar(self, boleto_emitido_id: int) -> dict | None:
        return self.client.get(f"/api/Boleto/{boleto_emitido_id}")

    def cancelar(self, boleto_emitido_id: int):
        return self.client.delete(f"/api/Boleto/{boleto_emitido_id}")

