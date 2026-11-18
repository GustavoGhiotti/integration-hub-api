from src.infrastructure.external.collectsys.providers.obter_dividas import ObterDivida
from src.domain.entities.contrato_parcelamento import ParcelamentoDivida
from src.shared.utils.xml_tratamentos import *

class DividaAtiva:
    @staticmethod
    def obter(id_cliente:int) -> ParcelamentoDivida:
        xml = ObterDivida("cobrança").consultar_por_id(id_cliente)
        
        cedente = extrair_tag(xml, "<NmCedente>", "</NmCedente>")
        id_cedente = int(extrair_tag(xml, "<IdCedente>", "</IdCedente>"))
        id_contratos = extrair_tags(xml, "IdContrato")

        return ParcelamentoDivida(nome_cedente=cedente
                                    ,id_cedente=id_cedente
                                    ,id_cliente=id_cliente
                                    ,id_contrato=id_contratos
                                    ,xml=xml)
        