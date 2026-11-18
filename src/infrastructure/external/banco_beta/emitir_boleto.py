from src.infrastructure.external.banco_beta.token import BancoBeta 
import requests


class Cartao(BancoBeta):
    def __init__(self):
        super().__init__()

    def emitir_ativo(self):
        url = f"{self.url_base}/v1/cartao-ativo/boleto"


    def emitir_creli(self):
        url = f"{self.url_base}/v1/creli/negociacao/boleto"
        headers= {"Authorization":f"Bearer {self.token}"}

        body = ""



        requests.post(url=url, data=body)

    def emitir_emprestimo():
        pass