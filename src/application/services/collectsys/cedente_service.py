from src.domain.entities.contrato import Contrato, Divida
from src.infrastructure.external.collectsys import Calcular
from src.shared.utils.xml_tratamentos import *

class Delta:
    def valor_entrada(contrato: Divida) -> Divida:
        xml = Calcular(contrato.nome_cedente, contrato.id_cliente,
                 contrato.id_cedente, 2, contrato.valor, contrato.xml,
                 contrato.data_pagamento).calcular_acordo_com_detalhes()

        valor_entrada = float(extrair_tag(xml, "<ValorParcela>", "</ValorParcela>"))
        contrato.valor = valor_entrada

        return contrato


class BancoBeta:
    def valor_entrada():
        pass
