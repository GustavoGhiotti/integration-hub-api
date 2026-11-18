from src.infrastructure.external.collectsys import *
from src.domain.exceptions.collectsys_exception import *
from src.domain.entities.cedentes import (
    CEDENTES_PARCELAMENTO_MIN_MAX,
    eh_carteira_cedente,
    identificar_carteira_cedente,
)
from src.domain.utils.ajusta_telefone import *
from unidecode import unidecode
from src.shared.utils import env_load, extrair_tag, montar_xml_dividas_para_tabular


CEDENTES_TABULAR_DIVIDA_ORIGINAL = CEDENTES_PARCELAMENTO_MIN_MAX


class TabularService:
    def __init__(self,servidor:str, id_cliente:int, id_acao:int, descricao:str, telefone:str):
        self.servidor = servidor
        self.carteira = identificar_carteira_cedente(servidor)
        self.id_cedente = self.carteira.id_cedente if self.carteira else None
        self.id_cliente = id_cliente
        self.id_acao = id_acao
        self.descricao = descricao
        self.ddd, self.telefone = ajusta_telefone(telefone)

    def _eh_cedente_com_divida_original(self) -> bool:
        servidor_id = str(self.servidor).strip()
        id_cedente = self.id_cedente or (int(servidor_id) if servidor_id.isdigit() else None)
        return (
            id_cedente in CEDENTES_TABULAR_DIVIDA_ORIGINAL
            or self._eh_carteira("beta", "teta", "teta special")
        )

    def _eh_carteira(self, *nomes: str) -> bool:
        return eh_carteira_cedente(self.servidor, *nomes)

    def vega(self, callid, detalheData, tipoEnvio, detalhe):
        tipoEnvio = str(tipoEnvio).strip().upper()
        detalhe = str(detalhe).strip().upper()

        if detalheData:
            detalheData = str(detalheData).strip()
            formatos_possiveis = [
                "%d/%m/%Y",
                "%Y/%m/%d",
                "%d-%m-%Y",
                "%Y-%m-%d",  ]

            for fmt in formatos_possiveis:
                try:
                    data_convertida = datetime.strptime(detalheData, fmt)
                    detalheData = data_convertida.strftime("%d/%m/%Y")
                    break
                except ValueError:
                    continue

        try:
            desc_acao = re.sub(r'[^A-Za-z0-9 ]+', '', unidecode(self.descricao))

            nm_detalhe, vlr_detalhe = [], []
            qtd_detalhe = 0

            id_acao = self.id_acao

            id_acao_detalhe_VAV = [102,103,104,105,157,158,159,160,162,163,164,165,166,167,168,169,170,171,172,173,
                                174,175,176,177,179]
            id_acao_detalhe_VHU = [99, 97, 98, 100]

            if id_acao in id_acao_detalhe_VAV:

                qtd_detalhe += 1
                nm_detalhe.append("CALLID")
                vlr_detalhe.append(callid)
                if len(vlr_detalhe) >= 1 and not vlr_detalhe[0]:
                    raise TabularException("ERRO: Sem preenchimento no campo obrigatório - callId (somente numeros)")

            if ((157 <= id_acao <= 166) or (171 <= id_acao <= 183)):
                inserir_acao_com_detalhe = Tabular(servidor = self.servidor,
                                id_cliente = self.id_cliente, id_acao = self.id_acao,
                                descricao_acao = desc_acao, telefone = self.telefone,
                                ddd = self.ddd).acao_com_detalhes(
                                nm_detalhe, vlr_detalhe, qtd_detalhe)

                codigo = extrair_tag(
                    inserir_acao_com_detalhe,
                    "<InserirAcaoComDetalheResult>",
                    "</InserirAcaoComDetalheResult>"
                )

                return {"Tabulacao": codigo}

            if not ((98 <= id_acao <= 100) or (134 <= id_acao <= 145) or (150 <= id_acao <= 156)):
                qtd_detalhe += 1
                match id_acao:
                    case 97:
                        nm_detalhe.append("AÇÃO - DATA PROMESSA")
                    case 135:
                        nm_detalhe.append("DATA PROMESSA PAGTO - DEBITO EM CONTA")
                    case 147 | 168:
                        nm_detalhe.append("DATA PROMESSA - INCORPORACAO")
                    case _:
                        nm_detalhe.append("DATA PROMESSA DE PAGAMENTO")
                vlr_detalhe.append(detalheData)

                if len(vlr_detalhe) >= 2 and not vlr_detalhe[1]:
                    raise TabularException(f"ERRO: Sem preenchimento no campo obrigatório para idAcao {id_acao} - detalheData (dia/mes/ano, ano/mes/dia, dia-mes-ano, ano-mes-dia)")

            if id_acao in (97, 102, 104, 169, 132, 148):
                qtd_detalhe += 1
                nm_detalhe.append("TIPO DE ENVIO")
                vlr_detalhe.append(tipoEnvio)

                if len(vlr_detalhe) >= 3 and not vlr_detalhe[2]:
                    raise TabularException(f"ERRO: Sem preenchimento no campo obrigatório para idAcao {id_acao} - tipoEnvio (e-mail, whatsapp, sms ou carta)")

            if id_acao in id_acao_detalhe_VHU:
                qtd_detalhe += 1
                match id_acao:
                    case 97:
                        nm_detalhe.append("DETALHE - IDENTIFICACAO POSITIVA - COM ACORDO")
                    case 98:
                        nm_detalhe.append("DETALHE - IDENTIFICACAO POSITIVA - SEM ACORDO")
                    case 99:
                        nm_detalhe.append("DETALHE - CONTATO EFETIVO")
                    case 100:
                        nm_detalhe.append("MOTIVO LIGAÇÃO IMPRODUTIVA")
                vlr_detalhe.append(detalhe)

                if len(vlr_detalhe) >= qtd_detalhe and not vlr_detalhe[-1]:
                    raise TabularException(f"ERRO: Sem preenchimento no campo obrigatório para idAcao {id_acao} - detalhe")

            if qtd_detalhe == 0:
                inserir_acao_com_detalhe = Tabular(servidor = self.servidor,
                                id_cliente = self.id_cliente, id_acao = self.id_acao,
                                descricao_acao = desc_acao, telefone = self.telefone,
                                ddd = self.ddd).acao()
                codigo = extrair_tag(
                    inserir_acao_com_detalhe,
                    "<InserirAcaoResult>",
                    "</InserirAcaoResult>"
                )

            else:
                inserir_acao_com_detalhe = Tabular(servidor = self.servidor,
                                id_cliente = self.id_cliente, id_acao = self.id_acao,
                                descricao_acao = desc_acao, telefone = self.telefone,
                                ddd = self.ddd).acao_com_detalhes(
                                nm_detalhe, vlr_detalhe, qtd_detalhe)
                codigo = extrair_tag(
                    inserir_acao_com_detalhe,
                    "<InserirAcaoComDetalheResult>",
                    "</InserirAcaoComDetalheResult>"
                )

            if "<RetornoErro>" in inserir_acao_com_detalhe:
                erro = extrair_tag(inserir_acao_com_detalhe, "<RetornoErro>", "</RetornoErro>")
                raise TabularException(erro)

            if codigo == "True":
                codigo = "Tabulado com Sucesso"


            return codigo

        except Exception as erro:
            raise TabularException(f"Erro interno ao tabular VEGA: {erro}")


    def cobranca(self, nm_detalhe=None, vlr_detalhe=None, qtd_detalhe=None):
        eh_mu = self._eh_carteira("mu")
        eh_nu = self._eh_carteira("nu")
        eh_delta_sem_bigger = self._eh_carteira("delta") and not self._eh_carteira("delta bigger")

        if self._eh_cedente_com_divida_original():
            dividas = ObterDivida("COBRANCA").consultar_por_id(self.id_cliente)

            mensagens = ["Nenhum cliente localizado com este CPFCNPJ.",
                        "O cliente não possui dívida ativa.",
                        "Cliente não localizado."]

            if (any(msg in dividas for msg in mensagens)):
                raise NenhumaDividaException("No momento, não constam dívidas ativas do cliente em nossa assessoria.")

            try:
                divida_xml = montar_xml_dividas_para_tabular(
                    dividas=dividas,
                    id_cliente=self.id_cliente,
                    servidor=self.servidor,
                    consultar_acordo=lambda id_acordo: ConsultarAcordo(
                        self.servidor,
                        self.id_cliente,
                        id_acordo,
                    ).consultar(),
                )
            except ValueError as erro:
                raise NenhumaDividaException(str(erro))

            resultado = Tabular(servidor = self.servidor, id_cliente = self.id_cliente,
                                id_acao = self.id_acao, descricao_acao = self.descricao,
                                telefone = self.telefone, ddd = self.ddd).acao_com_divida(divida_xml)
            if "True" in resultado:
                resultado = "Tabulado com Sucesso"
            else:
                if resultado == '':
                    resultado = "Erro ao tabular"
                else:
                    resultado = resultado
            return resultado

        if (eh_mu or eh_delta_sem_bigger) and self.id_acao == 252:

            nm_detalhe = [nm_detalhe]
            vlr_detalhe = [vlr_detalhe]
            qtd_detalhe = qtd_detalhe

            resultado = Tabular(servidor = self.servidor, id_cliente = self.id_cliente,
                                id_acao = self.id_acao, descricao_acao = self.descricao,
                                telefone = self.telefone, ddd = self.ddd).acao_com_detalhes(nm_detalhe, vlr_detalhe, qtd_detalhe)
            codigo = extrair_tag(
                    resultado,
                    "<InserirAcaoComDetalheResult>",
                    "</InserirAcaoComDetalheResult>"
                )

        elif eh_mu and self.id_acao == 687:

            nm_detalhe = "CLIENTE DEMOSTROU INTERESSE?"
            vlr_detalhe = "SIM"
            qtd_detalhe = 1
            resultado = Tabular(servidor = self.servidor, id_cliente = self.id_cliente,
                                id_acao = self.id_acao, descricao_acao = self.descricao,
                                telefone = self.telefone, ddd = self.ddd).acao_com_detalhes(nm_detalhe, vlr_detalhe, qtd_detalhe)
            codigo = extrair_tag(
                    resultado,
                    "<InserirAcaoComDetalheResult>",
                    "</InserirAcaoComDetalheResult>"
                )

        elif eh_nu and self.id_acao in (470, 471, 687):
            if self.id_acao == 687 and eh_nu:
                nm_detalhe = ["CLIENTE PAROU DE RESPONDER","CLIENTE DEMOSTROU INTERESSE?"]
                vlr_detalhe = ["APOS PROPOSTA","SIM"]
                qtd_detalhe = 2
            else:
                nm_detalhe = "PROXIMO CONTATO C/ CLIENTE"
                vlr_detalhe = "WHATSAPP"
                qtd_detalhe = 1

            resultado = Tabular(servidor = self.servidor, id_cliente = self.id_cliente,
                                id_acao = self.id_acao, descricao_acao = self.descricao,
                                telefone = self.telefone, ddd = self.ddd).acao_com_detalhes(nm_detalhe, vlr_detalhe, qtd_detalhe)
            codigo = extrair_tag(
                    resultado,
                    "<InserirAcaoComDetalheResult>",
                    "</InserirAcaoComDetalheResult>"
                )
        else:
            resultado = Tabular(servidor = self.servidor, id_cliente = self.id_cliente,
                                id_acao = self.id_acao, descricao_acao = self.descricao,
                                telefone = self.telefone, ddd = self.ddd).acao()
            codigo = extrair_tag(
                    resultado,
                    "<InserirAcaoResult>",
                    "</InserirAcaoResult>"
                )

        if "<RetornoErro>" in resultado:
            erro = extrair_tag(resultado, "<Mensagem>", "</Mensagem>")

            raise TabularException(erro)

        else:
            if codigo == "True":
                resultado = "Tabulado com Sucesso"
            return resultado


