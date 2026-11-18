from typing import Protocol

from src.infrastructure.external.collectsys.credentials.credentials import CollectSysCredentials


class CollectSysCarteiraProtocol(Protocol):
    @property
    def nome(self) -> str:
        ...

    @property
    def url(self) -> str:
        ...

    def obter_credenciais(self, id_cedente: int | None = None) -> CollectSysCredentials:
        ...

    