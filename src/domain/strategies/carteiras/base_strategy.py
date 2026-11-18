from abc import ABC, abstractmethod
from datetime import date
from dataclasses import dataclass

@dataclass
class RetornoCarteiraBase:
    con


class CarteiraBaseStrategy(ABC):
    @abstractmethod
    def valor_entrada(self) -> float:
        pass
    
    @abstractmethod
    def data_limite(self) -> date:
        pass

    @abstractmethod
    def parcela_max(self) -> int:
        pass
    
    @abstractmethod
    def desconto_max(self) -> int:
        pass
    
    @abstractmethod
    def contratos_negociar(self) -> list:
        pass

    @abstractmethod
    def parcelas_negociar(self) -> int:
        pass
        
    @abstractmethod
    def retorno_carteira(self) -> RetornoCarteiraBase: 
        pass


class CarteiraBaseStategyDetalhes(ABC):
    @abstractmethod
    def montar_xml(cls):
        pass
