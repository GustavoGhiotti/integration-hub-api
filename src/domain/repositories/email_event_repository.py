from abc import ABC, abstractmethod


class EmailEventRepository(ABC):
    """Contrato do repositório de eventos do SendGrid.

    Fluxo: a rota /webhook só chama `salvar_raw` (ingestão rápida e durável).
    O consumidor em background usa `reivindicar_lote` -> `gravar_eventos` ->
    `marcar_processados` / `marcar_falha`, além das rotinas de manutenção.
    """

    # ---- Ingestão (rota /webhook) ----
    @abstractmethod
    def salvar_raw(self, headers: str, body: str):
        ...

    # ---- Consumidor em background ----
    @abstractmethod
    def reivindicar_lote(self, limite: int) -> list:
        ...

    @abstractmethod
    def gravar_detalhe(self, eventos: list):
        ...

    @abstractmethod
    def agregar_lote(self, limite: int) -> int:
        ...

    @abstractmethod
    def marcar_processados(self, ids: list):
        ...

    @abstractmethod
    def marcar_falha(self, ids: list, erro: str | None = None):
        ...

    @abstractmethod
    def marcar_erro_parse(self, ids: list, motivo: str):
        ...

    # ---- Manutenção ----
    @abstractmethod
    def resetar_processando(self) -> int:
        ...

    @abstractmethod
    def limpar_raw_antigo(self, dias: int) -> int:
        ...

    @abstractmethod
    def metricas_saude(self) -> dict:
        ...
