from datetime import date, timedelta

from src.infrastructure.external.collectsys.consulta_contrato_detalhe import ConsultaContratoDetalhe
from src.shared.utils.data import validacao_dia_util
from src.shared.utils.xml_tratamentos import normalizar_nome

from .default_rule import DefaultCedenteRule


class DeltaCedenteRule(DefaultCedenteRule):
    # Cedente 65. O 73 (Bigger) herda desta regra, mas mantem o
    # comportamento padrao ao cair no super() pelo guard de id_cedente.
    ID_CEDENTE = 65

    # Formalizacao/calculo em D+5.
    DIAS_VENCIMENTO = 5

    # Desconto fixo de 200 para todos os casos.
    DESCONTO = 200

    # Produto que so aceita acordo a vista, salvo quando o IDT_20 libera o
    # parcelamento/reparcelamento do contrato inteiro.
    PRODUTO_SOMENTE_AVISTA = "CONSIGNADO"
    IDT_20_LIBERA_PARCELAMENTO = "SEM VINCULO"

    DETALHES = [
        ["TIPO PAGAMENTO DELTA", "BOLETO", 2805, "Acordo", "Manual"],
        ["VALOR INTEGRAL PARCELA", "", 1237, "Acordo", "Manual"],
        ["VALOR DESCONTO PARCELA", "", 1238, "Acordo", "Manual"],
        ["VALOR MINIMO POLITICA", "", 1239, "Acordo", "Manual"],
    ]

    def consultar_contexto_produto(self, id_cliente: int, id_contrato: int):
        # O produto real e o vinculo (IDT_20) ficam nos detalhes do contrato,
        # nao na divida. Uma unica consulta resolve o nome exibido e a regra de
        # parcelamento (produto consignado so parcela quando IDT_20 = SEM VINCULO).
        detalhes = ConsultaContratoDetalhe(id_cliente, id_contrato).consultar_detalhes_delta()

        partes = [
            valor.strip()
            for valor in (detalhes.get("produto"), detalhes.get("idt20"))
            if valor and valor.strip()
        ]
        produto = " - ".join(partes) if partes else None

        produto_norm = normalizar_nome(detalhes.get("produto") or "")
        idt20_norm = normalizar_nome(detalhes.get("idt20") or "")
        somente_avista = (
            self.PRODUTO_SOMENTE_AVISTA in produto_norm
            and idt20_norm != self.IDT_20_LIBERA_PARCELAMENTO
        )

        if produto is None and not somente_avista:
            return None

        return {
            "produto": produto,
            "informativo": False,
            "somente_avista": somente_avista,
        }

    def montar_xml(self, context):
        if context.id_cedente != self.ID_CEDENTE:
            return super().montar_xml(context)

        # O calculo do Delta usa CalcularAcordoComDetalhe, que envia
        # self.xml_divida direto (nao passa por montar_xml_divida_calcular_acordo).
        # Por isso o filtro por condicao (parcelas em atraso escolhidas) e
        # aplicado aqui, uma unica vez.
        self._aplicar_condicao_xml(context)
        context.desconto = self.DESCONTO
        self.definir_data_vencimento(context)
        self.atualizar_detalhes(context, [detalhe[:] for detalhe in self.DETALHES])

    def montar_xml_divida_calcular_acordo(self, calcular, parcelado: str = "") -> str:
        if calcular.id_cedente != self.ID_CEDENTE:
            return super().montar_xml_divida_calcular_acordo(calcular, parcelado)
        return self._xml_por_condicao(calcular)

    def tipo_negociacao(
        self,
        condicao,
        total_parcelas: int | None = None,
        quantidade_em_atraso: int | None = None,
    ) -> str | None:
        # O rotulo reflete o que realmente e enviado ao calculo.
        quantidade_condicao = self._quantidade_parcelas_condicao(condicao)

        # Sem condicao informada (ou cobrindo todas as parcelas) o parcelamento
        # abrange o contrato inteiro: e um reparcelamento do contrato.
        if quantidade_condicao is None or (
            total_parcelas and quantidade_condicao >= total_parcelas
        ):
            return "reparcelamento do contrato"

        if quantidade_em_atraso and quantidade_condicao >= quantidade_em_atraso:
            return "todas em atraso"

        return "parcial em atraso"

    def definir_data_vencimento(self, context):
        if context.id_cedente != self.ID_CEDENTE:
            return super().definir_data_vencimento(context)

        if getattr(context, "data_vencimento", None):
            return

        if not context.vencimento:
            context.vencimento = date.today() + timedelta(days=self.DIAS_VENCIMENTO)

        context.data_vencimento = validacao_dia_util(context.vencimento)

    def _aplicar_condicao_xml(self, context):
        if getattr(context, "_delta_condicao_aplicada", False):
            return
        context._delta_condicao_aplicada = True
        context.xml_divida = self._xml_por_condicao(context)

    def _xml_por_condicao(self, calcular) -> str:
        quantidade_parcelas = self._quantidade_parcelas_condicao(getattr(calcular, "condicao", None))
        if quantidade_parcelas is None:
            return calcular.xml_divida

        maior_numero_prestacao = self._maior_numero_prestacao(calcular.xml_divida)
        if (
            maior_numero_prestacao is not None
            and quantidade_parcelas >= maior_numero_prestacao
        ):
            # Quitacao: paga todas as parcelas do contrato.
            return calcular.xml_divida

        return self.filtrar_xml_divida_por_condicao(calcular)
