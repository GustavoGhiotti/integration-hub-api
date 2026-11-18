import requests

class BancoBeta:
    def __init__(self):
        self.url_base = "https://api.bancobeta.com.br"
        self.token = self._token()


    def _token(self):
        url = f"{self.url_base}/v1/creli/negociacao/boleto"
        headers= {"Authorization":f"Bearer {self.token}"}

        body = ""

        result = requests.post(url=url, data=body)

        return 
