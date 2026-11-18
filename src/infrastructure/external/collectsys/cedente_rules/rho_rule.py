from datetime import date, timedelta
import logging
import re

from src.shared.utils.data import validacao_dia_util
from src.shared.utils.xml_tratamentos import extrair_array, extrair_tag, normalizar_nome

from .default_rule import DefaultCedenteRule
from .types import normalize_text


logger = logging.getLogger(__name__)


MENSAGEM_ATUALIZACAO_CADASTRAL = (
    "É necessário atualizar as informações cadastrais do cliente."
)
MENSAGEM_PRAZO_FORA_POLITICA = (
    "Prazo máximo da proposta de acordo está fora da política de Acordo."
)
MENSAGEM_VALOR_MINIMO_PARCELA = "Valor da parcela deve ser de no mínimo R$ {valor}."
MENSAGEM_VALOR_MINIMO_ENTRADA = "Valor de entrada deve ser de no mínimo R$ {valor}."
MENSAGEM_PARCIAL_SOMENTE_AVISTA = (
    "Negociação de parcelas em atraso é permitida somente à vista. "
    "Para parcelar, o acordo deve incluir todas as parcelas do contrato, "
    "em atraso e a vencer."
)
MENSAGEM_ACORDO_ATIVO_PRODUTO = (
    "Cliente já possui acordo ativo no produto {produto}. "
    "É permitido apenas um acordo por produto."
)
MENSAGEM_PRODUTOS_MESCLADOS = (
    "Não é possível gerar acordo com parcelas de produtos diferentes. "
    "Selecione parcelas de um único produto."
)

TIPO_NEGOCIACAO_QUITACAO = "quitacao"
TIPO_NEGOCIACAO_PARCELAS_EM_ATRASO = "parcelas em atraso"

PRODUTO_CARTAO = "cartao"
PRODUTO_EMPRESTIMO = "emprestimo"
PRODUTO_LIMITE = "limite"

# A API do Rho aceita qualquer plano e so devolve o erro depois de gerar o
# acordo. O limite por produto precisa ser aplicado aqui para nao calcular
# parcelamento fora da politica da carteira.
LIMITE_PARCELAS_POR_PRODUTO = {
    PRODUTO_CARTAO: 18,
    PRODUTO_EMPRESTIMO: 36,
    PRODUTO_LIMITE: 36,
}

# O produto e identificado pelo contrato lojista (contrato do cedente):
# iniciando com A e emprestimo, iniciando com M e limite e somente numeros e cartao.
PREFIXO_PRODUTO = {
    "A": PRODUTO_EMPRESTIMO,
    "M": PRODUTO_LIMITE,
}

NOME_PRODUTO = {
    PRODUTO_CARTAO: "CARTAO",
    PRODUTO_EMPRESTIMO: "EMPRESTIMO",
    PRODUTO_LIMITE: "LIMITE",
}

NOME_DETALHE_CONTRATO_LOJISTA = "CONTRATO LOJISTA"


class RhoCedenteRule(DefaultCedenteRule):
    cedente_ids = (43,)
    # Menor limite da carteira: usado quando o produto nao pode ser identificado.
    limite_max_parcelas = 18
    valor_minimo_parcela = 50.0
    valor_minimo_entrada = 50.0

    @staticmethod
    def _formatar_valor(valor: float) -> str:
        return f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")

    @staticmethod
    def _contrato_lojista(xml_divida: str | None) -> str:
        """Contrato do cedente da divida (campo CONTRATO LOJISTA no cadastro)."""
        xml = xml_divida or ""
        contrato = (
            extrair_tag(xml, "<Identificador>", "</Identificador>")
            or extrair_tag(xml, "<ContratoCedente>", "</ContratoCedente>")
            or extrair_tag(xml, "<DividaCedente>", "</DividaCedente>")
            or RhoCedenteRule._valor_detalhe(xml, NOME_DETALHE_CONTRATO_LOJISTA)
            or ""
        )
        return re.sub(r"[^0-9A-Z]", "", contrato.strip().upper())

    @staticmethod
    def _valor_detalhe(xml: str, nome: str) -> str | None:
        detalhes_xml = extrair_tag(
            xml, "<ArrayOfContratoDetalhe>", "</ArrayOfContratoDetalhe>"
        )
        if not detalhes_xml:
            return None

        nome_normalizado = normalizar_nome(nome)
        while "<ContratoDetalhe>" in detalhes_xml:
            detalhe = extrair_array(detalhes_xml, "<ContratoDetalhe>", "</ContratoDetalhe>")
            if not detalhe:
                break

            nome_detalhe = normalizar_nome(
                extrair_tag(detalhe, "<NomeDetalhe>", "</NomeDetalhe>") or ""
            )
            if nome_detalhe == nome_normalizado:
                return extrair_tag(detalhe, "<Valor>", "</Valor>")

            detalhes_xml = detalhes_xml.replace(detalhe, "", 1)

        return None

    def descrever_produto(self, xml_divida: str | None, nm_produto: str | None = None) -> str | None:
        # Produto nao identificado mantem o nome que veio da carteira.
        return NOME_PRODUTO.get(self.identificar_produto(xml_divida)) or nm_produto

    def produtos_xml_divida(self, xml_divida: str | None) -> set[str]:
        """Produtos distintos entre as dividas informadas."""
        produtos = set()
        xml_restante = xml_divida or ""

        while "<DividaAtiva>" in xml_restante:
            divida = extrair_array(xml_restante, "<DividaAtiva>", "</DividaAtiva>")
            if not divida:
                break

            produto = self.identificar_produto(divida)
            if produto:
                produtos.add(produto)

            xml_restante = xml_restante.replace(divida, "", 1)

        return produtos

    def mensagem_produtos_mesclados(self, xml_divida: str | None) -> str | None:
        # Um acordo nao pode misturar cartao, emprestimo e limite.
        if len(self.produtos_xml_divida(xml_divida)) > 1:
            return MENSAGEM_PRODUTOS_MESCLADOS

        return None

    @classmethod
    def mensagem_acordo_ativo_produto(cls, produto: str | None) -> str:
        return MENSAGEM_ACORDO_ATIVO_PRODUTO.format(
            produto=NOME_PRODUTO.get(produto, produto)
        )

    def condicao_cobre_contrato(self, condicao, total_parcelas: int | None) -> bool:
        """A negociacao inclui todas as parcelas do contrato?

        Sem condicao informada o contrato inteiro e enviado ao WS, entao a
        negociacao cobre tudo. Com condicao, cobre tudo apenas quando alcanca
        o total de parcelas do contrato.
        """
        quantidade = self._quantidade_parcelas_condicao(condicao)
        if quantidade is None:
            return True

        return bool(total_parcelas) and quantidade >= int(total_parcelas)

    def tipo_negociacao(
        self,
        condicao,
        total_parcelas: int | None = None,
        quantidade_em_atraso: int | None = None,
    ) -> str | None:
        return (
            TIPO_NEGOCIACAO_QUITACAO
            if self.condicao_cobre_contrato(condicao, total_parcelas)
            else TIPO_NEGOCIACAO_PARCELAS_EM_ATRASO
        )

    def mensagem_negociacao_parcial_invalida(
        self,
        condicao,
        plano: int,
        total_parcelas: int | None = None,
    ) -> str | None:
        # Parcelamento so e permitido na quitacao do contrato.
        try:
            plano_solicitado = int(plano or 1)
        except (TypeError, ValueError):
            plano_solicitado = 1

        if plano_solicitado <= 1 or self.condicao_cobre_contrato(condicao, total_parcelas):
            return None

        return MENSAGEM_PARCIAL_SOMENTE_AVISTA

    @staticmethod
    def _marcar_todas_dividas(xml_divida: str) -> str:
        """Marca todas as dividas do XML como selecionadas.

        O WS monta o acordo apenas com as dividas <Marcado>true</Marcado>. As
        parcelas a vencer chegam com false, entao sem isso a quitacao sairia
        somente com as vencidas.
        """
        return re.sub(
            r"<Marcado>\s*false\s*</Marcado>",
            "<Marcado>true</Marcado>",
            xml_divida or "",
            flags=re.IGNORECASE,
        )

    def montar_xml_divida_calcular_acordo(self, calcular, parcelado: str = "") -> str:
        # Mesmo critério da Nu: condicao que alcanca o contrato inteiro
        # negocia tudo (inclusive a vencer); abaixo disso, apenas as parcelas
        # mais atrasadas entram no acordo.
        quantidade_parcelas = self._quantidade_parcelas_condicao(getattr(calcular, "condicao", None))
        maior_numero_prestacao = self._maior_numero_prestacao(calcular.xml_divida)
        if (
            quantidade_parcelas is not None
            and maior_numero_prestacao is not None
            and quantidade_parcelas >= maior_numero_prestacao
        ):
            return self._marcar_todas_dividas(calcular.xml_divida)

        # Na negociacao parcial o filtro ja deixou so as parcelas escolhidas;
        # marca-las garante que todas entrem no acordo.
        return self._marcar_todas_dividas(self.filtrar_xml_divida_por_condicao(calcular))

    @classmethod
    def identificar_produto(cls, xml_divida: str | None) -> str | None:
        contrato = cls._contrato_lojista(xml_divida)
        if not contrato:
            return None

        produto = PREFIXO_PRODUTO.get(contrato[0])
        if produto:
            return produto

        return PRODUTO_CARTAO if contrato.isdigit() else None

    def limite_parcelas_divida(self, xml_divida: str | None = None) -> int:
        produto = self.identificar_produto(xml_divida)
        limite = LIMITE_PARCELAS_POR_PRODUTO.get(produto, self.limite_max_parcelas)
        if produto is None and xml_divida:
            logger.warning(
                "rho_produto_nao_identificado contrato_lojista=%s limite=%s",
                self._contrato_lojista(xml_divida),
                limite,
            )
        return limite

    @classmethod
    def mensagem_valor_minimo_parcela(cls, valor: float | None = None) -> str:
        valor = cls.valor_minimo_parcela if valor is None else valor
        return MENSAGEM_VALOR_MINIMO_PARCELA.format(valor=cls._formatar_valor(valor))

    @classmethod
    def mensagem_valor_minimo_entrada(cls) -> str:
        return MENSAGEM_VALOR_MINIMO_ENTRADA.format(
            valor=cls._formatar_valor(cls.valor_minimo_entrada)
        )

    @classmethod
    def _atende_minimo(cls, valor: float, minimo: float | None = None) -> bool:
        # O minimo da carteira e inclusivo: R$ 50,00 exatos e aceito.
        minimo = cls.valor_minimo_parcela if minimo is None else minimo
        return valor >= minimo

    def mensagem_valor_entrada_invalido(self, valor_entrada, plano: int) -> str | None:
        # A API do Rho aceita a entrada informada e so recusa o acordo depois.
        # Valida antes para nao devolver uma simulacao invalida ao cliente.
        try:
            valor = float(valor_entrada or 0)
        except (TypeError, ValueError):
            return None

        # Entrada zerada/nao informada deixa o proprio WS calcular o valor.
        if valor > 0 and not self._atende_minimo(valor, self.valor_minimo_entrada):
            return self.mensagem_valor_minimo_entrada()

        return None

    @staticmethod
    def _extrair_valor_minimo_parcela(resultado: str) -> float | None:
        mensagem = normalize_text(resultado)
        if "valor da parcela" not in mensagem or "valor minimo" not in mensagem:
            return None

        correspondencia = re.search(
            r"valor\s+minimo\s*:?\s*(?:r\$\s*)?([0-9][0-9.,]*)",
            mensagem,
        )
        if not correspondencia:
            return None

        valor = correspondencia.group(1)
        if "," in valor:
            valor = valor.replace(".", "").replace(",", ".")
        try:
            return float(valor)
        except ValueError:
            return None

    async def obter_parcelamento_max(
        self,
        contrato,
        executar_calculo,
        limite_max_parcelas: int = 36,
    ) -> None:
        """Define o teto direto pelo limite do produto.

        A API do Rho aceita qualquer plano e nunca devolve erro na
        varredura, entao testar plano por plano so gastava chamadas. O maior
        plano real e definido depois, em valores_parcelados, descartando as
        simulacoes com parcela abaixo do minimo.
        """
        limite = min(limite_max_parcelas, self.limite_parcelas_divida(contrato.xml))
        contrato.parcelamento_max = max(1, limite)
        logger.info(
            "rho_parcelamento_max id_cliente=%s id_contrato=%s produto=%s parcela_max=%s",
            contrato.id_cliente,
            contrato.id_contrato,
            self.identificar_produto(contrato.xml),
            contrato.parcelamento_max,
        )

    def quantidades_parcelamento(
        self, quantidades: set[int], parcelamento_max: int, contrato=None
    ) -> set[int]:
        # O Rho somente confirma o valor real depois do CalcularAcordo. Por isso,
        # todos os planos precisam ser simulados antes de definir o maior plano válido.
        limite = self.limite_parcelas_divida(getattr(contrato, "xml", None))
        return set(range(1, min(parcelamento_max, limite) + 1))

    def resultado_calculo_parcelas_valido(self, resultado: str, parcelas: int) -> bool:
        valores = self._valores_parcelas_calculadas(resultado)
        quantidade_valores_esperada = 1 if parcelas == 1 else 2
        return (
            len(valores) >= quantidade_valores_esperada
            and self._atende_minimo(valores[0])
            and (
                parcelas == 1
                or all(self._atende_minimo(valor) for valor in valores[1:])
            )
        )

    @staticmethod
    def _valores_parcelas_calculadas(resultado: str) -> list[float]:
        valores = []
        restante = resultado or ""
        while "<ParcelaAcordo>" in restante:
            parcela = extrair_array(restante, "<ParcelaAcordo>", "</ParcelaAcordo>")
            if not parcela:
                break
            valor = extrair_tag(parcela, "<ValorParcela>", "</ValorParcela>")
            try:
                valores.append(float(str(valor).replace(",", ".")))
            except (TypeError, ValueError):
                return []
            restante = restante.replace(parcela, "", 1)
        return valores

    def mensagem_resultado_calculo_invalido(self, resultado: str, parcelas: int) -> str:
        return self.mensagem_valor_minimo_parcela()

    def mensagem_parcelamento_maximo(self, parcelamento_maximo: int) -> str:
        return (
            f"O valor mínimo permitido por parcela é R$ "
            f"{self._formatar_valor(self.valor_minimo_parcela)}. "
            f"Para este acordo, o máximo disponível é de {parcelamento_maximo} parcelas."
        )

    def selecionar_contratos_parcelados(self, contratos: list):
        if len(contratos) <= 4:
            return sorted(contratos, key=lambda contrato: contrato.qtd_parcelas)

        contratos_por_parcela = {
            contrato.qtd_parcelas: contrato
            for contrato in contratos
        }
        parcelas_disponiveis = sorted(contratos_por_parcela)
        maior_parcelamento = parcelas_disponiveis[-1]
        alvos = (
            parcelas_disponiveis[0],
            int(maior_parcelamento / 3 + 0.5),
            int((maior_parcelamento * 2) / 3 + 0.5),
            maior_parcelamento,
        )
        selecionadas = set()
        for alvo in alvos:
            parcela = min(
                parcelas_disponiveis,
                key=lambda disponivel: (abs(disponivel - alvo), disponivel),
            )
            selecionadas.add(parcela)

        while len(selecionadas) < min(4, len(parcelas_disponiveis)):
            restantes = [p for p in parcelas_disponiveis if p not in selecionadas]
            parcela = max(
                restantes,
                key=lambda candidato: (
                    min(abs(candidato - escolhida) for escolhida in selecionadas),
                    candidato,
                ),
            )
            selecionadas.add(parcela)

        return [contratos_por_parcela[p] for p in sorted(selecionadas)]

    @staticmethod
    def _data_maxima_pagamento(hoje: date) -> date:
        data_maxima = hoje + timedelta(days=2)
        while data_maxima.weekday() in (5, 6):
            data_maxima += timedelta(days=1)
        return data_maxima

    def definir_data_vencimento(self, context):
        if getattr(context, "data_vencimento", None):
            return

        data_maxima = self._data_maxima_pagamento(date.today())
        data_solicitada = context.vencimento or data_maxima
        context.vencimento = min(data_solicitada, data_maxima)
        context.data_vencimento = validacao_dia_util(context.vencimento)

    def tratar_erro_formalizacao(self, resultado: str) -> str:
        mensagem = normalize_text(resultado)
        valor_minimo = self._extrair_valor_minimo_parcela(resultado)
        if valor_minimo is not None:
            return self.mensagem_valor_minimo_parcela(valor_minimo)

        sinais_erro_prazo = (
            "prazo maximo da proposta de acordo",
            "fora da politica de acordo",
        )
        sinais_erro_cadastral = (
            "proposta",
            "fora da politica",
        )

        # O erro de prazo tambem contem "proposta" e "fora da politica",
        # mas deve ser devolvido sem ser convertido em erro cadastral.
        if all(sinal in mensagem for sinal in sinais_erro_prazo):
            return MENSAGEM_PRAZO_FORA_POLITICA

        if all(sinal in mensagem for sinal in sinais_erro_cadastral):
            return MENSAGEM_ATUALIZACAO_CADASTRAL

        return resultado
