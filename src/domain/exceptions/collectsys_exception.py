from src.shared.utils import extrair_tag

class CollectSysException(Exception):
    def __init__(self, *,mensagem):
        super().__init__(mensagem)
        self.mensagem = mensagem

    def erro(self)-> str:
        resultado = extrair_tag(self.mensagem, "<Mensagem>", "</Mensagem>")
        if not resultado:
            resultado = self.mensagem
        return resultado
    
class NenhumaDividaException(Exception):
    pass

class InfobipNumeroIndisponivelException(Exception):
    pass

class CodigoPixException(Exception):
    pass

class RetornoTratadoBeta(Exception):
    pass

class ErroCalculoDivida(CollectSysException):
    def __init__(self, *,mensagem):
        super().__init__(mensagem)

class ErroFormalizarAcordo(Exception):
    def __init__(self, *,mensagem):
        super().__init__(mensagem)
        self.mensagem = mensagem

    def erro(self)-> str:
        return extrair_tag(self.mensagem, "<Mensagem>", "</Mensagem>")

class ClienteNaoEncontrado(CollectSysException):
   def __init__(self, *,mensagem):
        super().__init__(mensagem)

    
class BoletoException(CollectSysException):
    def __init__(self, *,mensagem):
        super().__init__(mensagem)



class ParcelamentoExceptiom(CollectSysException):
   def __init__(self, *,mensagem):
        super().__init__(mensagem)

class TabularException(Exception):
    pass

class CodigoPixException(Exception):
    pass
