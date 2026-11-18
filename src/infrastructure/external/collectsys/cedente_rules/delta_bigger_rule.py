from .delta_rule import DeltaCedenteRule


class DeltaBiggerCedenteRule(DeltaCedenteRule):
    # Cedente 73. Herda do Delta (65), mas mantem o comportamento padrao:
    # montar_xml / definir_data_vencimento / montar_xml_divida_calcular_acordo
    # ja caem no super() pelo guard de id_cedente. tipo_negociacao e
    # consultar_contexto_produto nao recebem o id_cedente, entao sao revertidos
    # explicitamente para o padrao (sem condicao e sem tratativa por produto).
    def consultar_contexto_produto(self, id_cliente: int, id_contrato: int):
        return None

    def tipo_negociacao(
        self,
        condicao,
        total_parcelas: int | None = None,
        quantidade_em_atraso: int | None = None,
    ) -> str | None:
        return None
