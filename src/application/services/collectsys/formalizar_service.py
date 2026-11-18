from src.infrastructure.external.collectsys import ConfirmarAcordo, ConsultarCliente, Tabular, DadosAcordo
from src.shared.utils.xml_tratamentos import *
import asyncio

class Formalizar:        
     def gerar(id_cliente:int, xml:str, id_cedente:str) -> int:
        id_acordo = ConfirmarAcordo(id_cedente, id_cliente, xml).formalizar()

        id_acordo = int(extrair_tag(id_acordo, "<ConfirmarAcordoResult>", "</ConfirmarAcordoResult>"))
        
        return id_acordo
        

   