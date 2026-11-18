from dataclasses import dataclass

from src.shared.utils.xml_tratamentos import *

class Mu:
    def grupo(xml) -> str:
        #Ajustar qual produto do Mu
        divida_cedente = str(extrair_tag(xml, "<DividaCedente>", "</DividaCedente>"))

        nr_divida_cedente = int(divida_cedente[0:3])

        match nr_divida_cedente:
            case 100:
                nome_cedente = "ETA"
            case 700:
                nome_cedente = "XICLUB"
            case _:
                nome_cedente = "MU"

        return nome_cedente

class Delta:
    def selecionar_contratos(xml:str) -> str:
        #Negociar contrato é necessário selecionar todas as parcelas
        return xml.replace("<Marcado>false</Marcado>", "<Marcado>true</Marcado>")

class BancoBeta:
    @staticmethod
    def mensagem_parcelamento_indisponivel() -> str:
        return "Proposta nao disponivel para esse contrato"

    @staticmethod
    def mensagem_sem_propostas() -> str:
        return "Não a propostas no momento"

    @staticmethod
    def eh_produto_cartao(nome_produto: str | None) -> bool:
        nome_produto_normalizado = (nome_produto or "").upper()
        if "CARTAO" not in nome_produto_normalizado:
            return False
        if "RENEG" in nome_produto_normalizado:
            return False
        if "EMPRESTIMO" in nome_produto_normalizado:
            return False
        return True

    @staticmethod
    def eh_erro_sem_parcelamento(mensagem: str | None) -> bool:
        mensagem_normalizada = normalizar_nome(mensagem or "")
        padroes = (
            "INDEX WAS OUT OF RANGE",
            "ARGUMENTNULLEXCEPTION",
            "QUANTIDADEPARCELAS",
            "NAO EXISTEM OPCOES DE PARCELAMENTO DE FATURA",
            "PARA ESSE CONTRATO DE CARTAO, NAO EXISTEM OPCOES DE PARCELAMENTO DE FATURA",
            "PARCELAMENTO NAO DISPONIVEL PARA ESSE CONTRATO",
        )
        return any(padrao in mensagem_normalizada for padrao in padroes)

    @staticmethod
    def eh_erro_sem_propostas(mensagem: str | None) -> bool:
        mensagem_normalizada = normalizar_nome(mensagem or "")
        return (
            "ARGUMENTNULLEXCEPTION" in mensagem_normalizada
            and "VALUE CANNOT BE NULL" in mensagem_normalizada
            and "PARAMETER NAME: SOURCE" in mensagem_normalizada
        )

    def valor_entrada(xml_divida:str, qtd_parcelas:int, valor_min, valor_max):
        valor_min = float(valor_min or 0)
        valor_max = float(valor_max or 0)

        if 21 <= qtd_parcelas <= 36:
            qtd = 9
        elif 11 <= qtd_parcelas <= 20:
            qtd = 7
        elif 5 <= qtd_parcelas <= 10:
            qtd = 5
        elif 2 <= qtd_parcelas <= 4:
            qtd = 3
        else:
            qtd = 1

        entrada = float(valor_max) / qtd
        if entrada < 50:
            entrada = 50
        if valor_min and entrada < valor_min:
            entrada = valor_min


        return round(entrada, 2)

    @staticmethod
    def detalhe_proposta(
        nome_produto: str | None,
        qtd_parcelas: int,
        cartao_35: str | None,
        condicao=None,
    ) -> dict | None:
        if BancoBeta.condicao_informada(condicao):
            return {
                "detalhe": "Pagamento das parcelas em atraso.",
            }

        eh_cartao = BancoBeta.eh_produto_cartao(nome_produto)

        if eh_cartao and cartao_35 == "SIM" and qtd_parcelas <= 1:
            return None

        if eh_cartao and cartao_35 == "SIM":
            return {
                "detalhe": "Parcelamento das faturas em atraso.",
            }

        return {
            "detalhe": "Renegociacao.",
        }

    @staticmethod
    def condicao_informada(condicao) -> bool:
        if isinstance(condicao, bool):
            return False

        condicao_normalizada = str(condicao or "").strip()
        if not condicao_normalizada.isdigit():
            return False

        return int(condicao_normalizada) > 0





CEDENTES_BETA = (81, 104)
CEDENTES_TETA_COMUM = (77, 84, 103)
CEDENTES_TETA = (*CEDENTES_TETA_COMUM, 99)
CEDENTES_COM_PRODUTO = (*CEDENTES_TETA, *CEDENTES_BETA)
# Cedentes cujo nome do produto so existe no detalhe do contrato, e nao na
# divida. Separado de CEDENTES_COM_PRODUTO porque aquele grupo tambem controla
# a exposicao de NumeroContratoBanco e contratosUtilizados na resposta.
CEDENTES_ARC = (90, 96)
CEDENTES_NU = (14,)
CEDENTES_ZETA = (71,)
CEDENTES_PRODUTO_NO_DETALHE = (*CEDENTES_COM_PRODUTO, 60, *CEDENTES_ARC, *CEDENTES_NU, *CEDENTES_ZETA)
CEDENTES_PARCELAMENTO_MIN_MAX = (77, 81, 84, 99, 103, 104)
CEDENTES_CALCULO_DETALHE = (60, 65, 51, 73, 64, 70,71, 83, 90, 96, 81, 77, 84, 99, 103, 104)


@dataclass(frozen=True)
class CarteiraCedente:
    id_cedente: int
    nome: str
    aliases: tuple[str, ...] = ()

    @property
    def nomes_busca(self) -> tuple[str, ...]:
        return (self.nome, *self.aliases)

    def possui_nome(self, nome: str) -> bool:
        nome_normalizado = normalizar_nome(nome)
        return any(normalizar_nome(alias) == nome_normalizado for alias in self.nomes_busca)


CEDENTES_CARTEIRAS = (
    CarteiraCedente(1, "VEGA", ("VEGA FINANCEIRA", "VGF")),
    CarteiraCedente(3, "MU", ("ETA", "XICLUB", "XI CLUB")),
    CarteiraCedente(4, "GAMA"),
    CarteiraCedente(14, "NU"),
    CarteiraCedente(43, "RHO", ("PAGSEGURO",)),
    CarteiraCedente(51, "BANCOALFA", ("BANCO ALFA",)),
    CarteiraCedente(60, "PI"),
    CarteiraCedente(64, "CEDENTE 64"),
    CarteiraCedente(65, "DELTA"),
    CarteiraCedente(70, "CEDENTE 70"),
    CarteiraCedente(71, "ZETA"),
    CarteiraCedente(73, "DELTA BIGGER", ("BIGGER",)),
    CarteiraCedente(77, "TETA", ("BANCO TETA",)),
    CarteiraCedente(81, "BETA", ("BANCO BETA",)),
    CarteiraCedente(84, "TETA SWAT", ("TETA", "BANCO TETA")),
    CarteiraCedente(83, "PHIPF"),
    CarteiraCedente(90, "ARC4", ("ARC 4",)),
    CarteiraCedente(96, "TETA ARC4 OMEGA", ("ARC4 OMEGA", "TETAARC4OMEGA")),
    CarteiraCedente(99, "TETA SPECIAL", ("TETA ESPECIAL",)),
    CarteiraCedente(103, "TETA", ("BANCO TETA",)),
    CarteiraCedente(104, "BETA", ("BANCO BETA",)),
)

CEDENTES_CARTEIRAS_POR_ID = {carteira.id_cedente: carteira for carteira in CEDENTES_CARTEIRAS}


def _id_cedente_por_valor(valor) -> int | None:
    try:
        valor_texto = str(valor or "").strip()
        return int(valor_texto) if valor_texto.isdigit() else None
    except (TypeError, ValueError):
        return None


def identificar_carteira_cedente(valor) -> CarteiraCedente | None:
    id_cedente = _id_cedente_por_valor(valor)
    if id_cedente is not None:
        return CEDENTES_CARTEIRAS_POR_ID.get(id_cedente)

    valor_normalizado = normalizar_nome(str(valor or ""))
    if not valor_normalizado:
        return None

    nomes_ordenados = []
    for carteira in CEDENTES_CARTEIRAS:
        for alias in carteira.nomes_busca:
            alias_normalizado = normalizar_nome(alias)
            nomes_ordenados.append((len(alias_normalizado), alias_normalizado, carteira))

    for _, alias_normalizado, carteira in sorted(nomes_ordenados, key=lambda item: item[0], reverse=True):
        if alias_normalizado == valor_normalizado or alias_normalizado in valor_normalizado:
            return carteira

    return None


def eh_carteira_cedente(valor, *nomes: str) -> bool:
    carteira = identificar_carteira_cedente(valor)
    if carteira:
        return any(carteira.possui_nome(nome) for nome in nomes)

    valor_normalizado = normalizar_nome(str(valor or ""))
    return any(normalizar_nome(nome) in valor_normalizado for nome in nomes)
