from abc import ABC, abstractmethod

class BaseConnection(ABC):
    @abstractmethod
    def _connect(self):
        pass

    @abstractmethod
    def execute(self, query:str, parametros:tuple, fetch:bool = False):
        pass