from src.infrastructure.external.collectsys.consulta_contrato_detalhe import ConsultaContratoDetalhe

from .default_rule import DefaultCedenteRule


class Arc4CedenteRule(DefaultCedenteRule):
    def consultar_contexto_produto(self, id_cliente: int, id_contrato: int):
        # A divida da ARC4 nao traz o produto; ele fica no detalhe do contrato,
        # com a nomenclatura TETA (PRODUTO NOME TETA).
        produto = ConsultaContratoDetalhe(id_cliente, id_contrato).consultar_produto_arc()
        if not produto:
            return None

        return {"produto": produto, "informativo": False}
