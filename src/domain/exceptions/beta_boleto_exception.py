from src.shared.utils import extrair_tag


class BetaBoletoException(Exception):
    def __init__(self, *, mensagem):
        super().__init__(mensagem)
        self.mensagem = mensagem

    def erro(self) -> str:
        return extrair_tag(self.mensagem, "<Mensagem>", "</Mensagem>") or str(self.mensagem)
