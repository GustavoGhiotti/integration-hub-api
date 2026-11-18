from __future__ import annotations

from abc import ABC
from datetime import date, timedelta

from src.domain.exceptions.collectsys_exception import ErroFormalizarAcordo, RetornoTratadoBeta
from src.shared.utils.data import validacao_dia_util
from src.shared.utils.xml_tratamentos import (
    extrair_array,
    extrair_nm_produto,
    extrair_tag,
    forcar_detalhe_vazio,
    gerar_xml_detalhe_calculo,
)

from .types import RuleDecision, normalize_text


class BaseCedenteRule(ABC):
    # Limite de parcelas do cedente. None significa "sem limite proprio".
    limite_max_parcelas: int | None = None

    def consultar_contexto_produto(self, id_cliente: int, id_contrato: int):
        return None

    def descrever_produto(self, xml_divida: str | None, nm_produto: str | None = None) -> str | None:
        """Nome do produto exposto na resposta.

        Cedentes que identificam o produto pela propria divida sobrescrevem
        para devolver um nome mais preciso que o cadastrado na carteira.
        """
        return nm_produto

    def mensagem_valor_entrada_invalido(self, valor_entrada, plano: int) -> str | None:
        """Mensagem quando a entrada informada nao respeita a politica do cedente."""
        return None

    def mensagem_negociacao_parcial_invalida(
        self,
        condicao,
        plano: int,
        total_parcelas: int | None = None,
    ) -> str | None:
        """Mensagem quando o plano nao e permitido para a condicao solicitada."""
        return None

    def mensagem_produtos_mesclados(self, xml_divida: str | None) -> str | None:
        """Mensagem quando as dividas do acordo pertencem a produtos diferentes."""
        return None

    def tipo_negociacao(
        self,
        condicao,
        total_parcelas: int | None = None,
        quantidade_em_atraso: int | None = None,
    ) -> str | None:
        """Tipo de negociacao exposto na resposta, quando o cedente usa condicao."""
        return None

    def identificar_produto(self, xml_divida: str | None) -> str | None:
        """Produto da divida, para cedentes que separam politica por produto."""
        return None

    def mensagem_acordo_ativo_produto(self, produto: str | None) -> str:
        """Mensagem de bloqueio quando o produto ja possui acordo ativo."""
        return "Cliente já possui acordo ativo neste produto."

    def limite_parcelas_divida(self, xml_divida: str | None = None) -> int | None:
        """Limite de parcelas da divida.

        Cedentes cujos produtos possuem limites diferentes sobrescrevem este
        metodo para decidir a partir do XML da divida.
        """
        return self.limite_max_parcelas

    def aplicar_produto_informativo_verifica(
        self, item: dict, contexto: dict, parcelas: list[dict], total_parcelas: int
    ) -> dict:
        return item

    def montar_produto_informativo_parcelado(
        self, contexto: dict, nome_cedente: str, id_cliente: int, id_contrato: int
    ) -> dict | None:
        return None

    def montar_produto_informativo_proposta(
        self, contexto: dict, id_contrato: int
    ) -> dict | None:
        return None

    def tratar_erro_formalizacao(self, resultado: str) -> str:
        return resultado

    def tratar_erro_emissao_boleto(self, resultado: str) -> str:
        return resultado

    def montar_xml_divida_calcular_acordo(self, calcular, parcelado: str = "") -> str:
        return calcular.xml_divida

    def valor_entrada_parcelamento(self, contrato, parcelas: int, valor_padrao: float) -> float:
        return valor_padrao

    def resultado_parcelamento_cache(self, contrato, parcelas: int) -> str | None:
        return None

    def quantidades_parcelamento(
        self, quantidades: set[int], parcelamento_max: int, contrato=None
    ) -> set[int]:
        return quantidades

    def resultado_calculo_parcelas_valido(self, resultado: str, parcelas: int) -> bool:
        return True

    def selecionar_contratos_parcelados(self, contratos: list):
        return None

    def mensagem_resultado_calculo_invalido(self, resultado: str, parcelas: int) -> str | None:
        return None

    def filtrar_xml_divida_por_condicao(self, calcular) -> str:
        quantidade_parcelas = self._quantidade_parcelas_condicao(getattr(calcular, "condicao", None))
        if quantidade_parcelas is None:
            return calcular.xml_divida

        return self._manter_parcelas_mais_atrasadas(calcular.xml_divida, quantidade_parcelas)

    def aplicar_condicao_xml_divida(self, calcular):
        if getattr(calcular, "xml_divida_condicao_aplicada", False):
            return

        xml_divida = self.filtrar_xml_divida_por_condicao(calcular)
        calcular.xml_divida_condicao_aplicada = True

        if xml_divida == calcular.xml_divida:
            return

        calcular.xml_divida = xml_divida
        calcular.nm_produto = extrair_nm_produto(xml_divida) or getattr(calcular, "nm_produto", None)

    def _quantidade_parcelas_condicao(self, condicao) -> int | None:
        if isinstance(condicao, bool):
            return None

        condicao_normalizada = str(condicao or "").strip().lower()
        if not condicao_normalizada.isdigit():
            return None

        quantidade = int(condicao_normalizada)
        return quantidade if quantidade > 0 else None

    def _manter_parcelas_mais_atrasadas(self, xml_divida: str, quantidade_parcelas: int) -> str:
        dividas = []
        xml_restante = xml_divida or ""
        ordem = 0

        while "<DividaAtiva>" in xml_restante:
            divida = extrair_array(xml_restante, "<DividaAtiva>", "</DividaAtiva>")
            if not divida:
                break

            atraso = int(extrair_tag(divida, "<Atraso>", "</Atraso>") or 0)
            if atraso > 0:
                dividas.append(
                    {
                        "xml": divida,
                        "atraso": atraso,
                        "data_vencimento": self._data_vencimento(divida),
                        "ordem": ordem,
                    }
                )

            xml_restante = xml_restante.replace(divida, "", 1)
            ordem += 1

        if not dividas:
            return xml_divida

        parcelas_selecionadas = sorted(
            dividas,
            key=lambda item: (-item["atraso"], item["data_vencimento"], item["ordem"]),
        )[:quantidade_parcelas]
        parcelas_selecionadas = sorted(parcelas_selecionadas, key=lambda item: item["ordem"])
        xml_parcelas = "".join(item["xml"] for item in parcelas_selecionadas)

        return f"<ArrayOfDividaAtiva>{xml_parcelas}</ArrayOfDividaAtiva>"

    def _maior_numero_prestacao(self, xml_divida: str) -> int | None:
        maior_numero_prestacao = None
        xml_restante = xml_divida or ""

        while "<DividaAtiva>" in xml_restante:
            divida = extrair_array(xml_restante, "<DividaAtiva>", "</DividaAtiva>")
            if not divida:
                break

            numero_prestacao = extrair_tag(divida, "<NumeroPrestacao>", "</NumeroPrestacao>")
            if numero_prestacao and numero_prestacao.isdigit():
                maior_numero_prestacao = max(
                    maior_numero_prestacao or 0,
                    int(numero_prestacao),
                )

            xml_restante = xml_restante.replace(divida, "", 1)

        return maior_numero_prestacao

    def _data_vencimento(self, divida: str) -> date:
        data_vencimento = extrair_tag(divida, "<DataVencimento>", "</DataVencimento>")
        if not data_vencimento:
            return date.max

        try:
            return date.fromisoformat(data_vencimento.split("T", 1)[0])
        except ValueError:
            return date.max

    def preparar_calculo_com_detalhes(self, calcular, produto, parcelado, cartao_35):
        calcular.operacao = "calcular_acordo_com_detalhes"
        calcular.produto = produto
        calcular.parcelado = parcelado
        calcular.cartao_35 = cartao_35
        calcular.nm_produto = extrair_nm_produto(calcular.xml_divida)
        calcular.plano = calcular.plano or 1
        calcular.valor_entrada = calcular.valor_entrada or 0

        defaults = {
            "desconto": 100,
            "detalhes": [],
            "data_vencimento": "",
            "detalhe_xml": "",
            "detalhe_xml_normalizado": "",
            "resultado": "",
            "resultado_tratado": "",
            "resultado_normalizado": "",
            "resultado_tratado_normalizado": "",
            "valido": True,
            "mensagem": None,
            "valor_minimo_entrada": None,
            "valor_maximo_entrada": None,
            "parcelamento_min": None,
            "parcelamento_max": None,
        }
        for atributo, valor in defaults.items():
            setattr(calcular, atributo, valor)

    def atualizar_retorno(self, context, resultado: str, resultado_tratado: str, valido: bool):
        context.resultado = resultado
        context.resultado_tratado = resultado_tratado
        context.resultado_normalizado = normalize_text(resultado)
        context.resultado_tratado_normalizado = normalize_text(resultado_tratado)
        context.valido = valido

    def montar_xml(self, context):
        if context.nm_produto is None:
            context.nm_produto = extrair_nm_produto(context.xml_divida)
        if context.plano is None:
            context.plano = context.plano or 1
        if context.valor_entrada is None:
            context.valor_entrada = context.valor_entrada or 0
        self.definir_data_vencimento(context)
        self.atualizar_detalhes(context, context.detalhes)

    def preparar_calculo(self, context):
        self.montar_xml(context)

    def tratar_retorno(self, context):
        return None

    def definir_data_vencimento(self, context):
        if getattr(context, "data_vencimento", None):
            return

        if context.id_cedente in (63, 73, 90) and not context.vencimento:
            context.vencimento = date.today() + timedelta(days=2)
        elif not context.vencimento:
            context.vencimento = date.today() + timedelta(days=6)

        context.data_vencimento = validacao_dia_util(context.vencimento)

    def atualizar_detalhes(self, context, detalhes, force_empty: bool | None = None):
        context.detalhes = detalhes
        if force_empty is None:
            force_empty = forcar_detalhe_vazio(context.id_cedente, detalhes)
        context.detalhe_xml = gerar_xml_detalhe_calculo(
            detalhes=detalhes,
            force_empty=force_empty,
        )
        context.detalhe_xml_normalizado = normalize_text(context.detalhe_xml)

    def finalizar_falha(self, context):
        raise ErroFormalizarAcordo(mensagem=context.resultado_tratado)

    def lancar_erro_inesperado(self, context):
        self.finalizar_falha(context)


class BetaLikeCedenteRule(BaseCedenteRule):
    def finalizar_falha(self, context):
        raise RetornoTratadoBeta(context.mensagem or context.resultado_tratado)
