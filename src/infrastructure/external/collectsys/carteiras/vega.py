from src.infrastructure.external.collectsys.credentials.credentials import CollectSysCredentials
from src.infrastructure.external.collectsys.credentials.credentials_provider import CollectSysCredentialsProvider
from src.infrastructure.external.collectsys.urls.url_provider import CollectSysUrlProvider 

class Vega:
    nome = "vega"

    def __init__(self, credentials_provider: CollectSysCredentialsProvider | None = None) -> None:
        self._credentials_provider = credentials_provider or CollectSysCredentialsProvider()
        
    def obter_credenciais(self, id_cedente: int | None = None) -> CollectSysCredentials:
        return self._credentials_provider.obter(id_cedente)

    @property
    def url(self) -> str:
        url_provider = CollectSysUrlProvider()
        return url_provider.base_url(self.nome)
    