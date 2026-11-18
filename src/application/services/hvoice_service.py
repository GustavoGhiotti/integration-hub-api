from src.infrastructure.repositories.sql_hvoice_repository import SqlHvoiceRepository
from src.domain.utils.metadados import ajustando_metadados_ligacoes_existentes
import os
import zipfile
import shutil
import threading
from datetime import datetime
from src.domain.utils.audios import (
    selecionado_audios_existentes_geral,
    selecionado_audios_existentes,
    salvando_arquivo_audio
)
from src.domain.utils.metadados import salvando_arquivo_metadado
import os, uuid, zipfile, pandas as pd

HVOICE_DOWNLOAD_BASE_URL = "https://api.empresa.example/hvoice/download"


def diretorio_hvoice_local() -> str:
    return os.path.join(os.getcwd(), "arquivos", "hvoice")


def diretorio_hvoice_publicado() -> str:
    return diretorio_hvoice_local()


# HOMOLOGACAO:
# Use esta versao no ambiente HML quando a pasta local de homologacao
# nao estiver publicada para acesso externo. Ela salva o ZIP direto no
# servidor da API de producao (.91) e mantem o link publico de producao.
#
# def diretorio_hvoice_publicado() -> str:
#     return (
#         r"\\10.0.0.91\c\inetpub\wwwroot\APISistemaAcme"
#         r"\arquivos\hvoice"
#     )


def remover_colunas_call_id(df):
    colunas_possiveis = [
        "[Call ID (Controle Interno)]",
        "Call ID (Controle Interno)",
        "[CALL ID (CONTROLE INTERNO)]",
        "CALL ID (CONTROLE INTERNO)",
        "[CALL ID TAB(CONTROLE INTERNO)]",
        "CALL ID TAB(CONTROLE INTERNO)"
    ]

    colunas_existentes = [c for c in colunas_possiveis if c in df.columns]

    if colunas_existentes:
        df = df.drop(columns=colunas_existentes)

    return df

class Hvoice:
    def __init__(self, cedente:str, data:str, min_minuto:int, max_minuto:int, faixa:str,
                 tabulacao: str, min_total_max:int, qtd_operador:int, data_final:str = None):
        self.cedente = cedente
        self.data = data
        self.data_final = data_final or data
        self.min_minuto = min_minuto
        self.max_minuto = max_minuto
        self.faixa = faixa
        self.tabulacao = tabulacao
        self.min_total_max = min_total_max
        self.qtd_operador = qtd_operador

    def metadados_vega(self):

        if isinstance(self.faixa, list):
            self.faixa = self.faixa[0] if self.faixa else ""
        if isinstance(self.tabulacao, list):
            self.tabulacao = self.tabulacao[0] if self.tabulacao else ""

        if not self.faixa:
            raise ValueError(" A faixa não foi informada. Exemplo: 'HABITACIONAL', 'COMERCIAL', etc.")
        if not self.tabulacao:
            raise ValueError(" A tabulação não foi informada. Exemplo: 'PROMESSA', 'NAO NEGOCIO', etc.")

        # Normaliza para comparação sem erro de None
        faixa_upper = self.faixa.strip().upper()
        tabulacao_upper = self.tabulacao.strip().upper()

        match faixa_upper :
            case "HABITACIONAL":
                self.faixa = ["_HABIT_FASES_"]
                dt_atraso = 31
            case "COMERCIAL":
                self.faixa = ["_COMER_FASES_"]
                dt_atraso = 31
            case "PAGAMENTO":
                self.faixa = ["PAGAMENTO JA EFETUADO"]
                dt_atraso = 31
            case "IMPRODUTIVAS" | "IMPRODUTIVA":
                self.faixa = ["IMPRODUTIVAS"]
                dt_atraso = 9999

        match tabulacao_upper:
            case "PROMESSA":
                self.tabulacao = [
                    "PROMESSA DE PAGAMENTO SEM EMISSÃO DE BOLETO",
                    "PROMESSA DE PAGAMENTO COM EMISSÃO DE BOLETO"
                ]
            case "NAO NEGOCIO":
                self.tabulacao = [
                    "CONTATO SEM NEGOCIAÇÃO",
                    "SEM CAPACIDADE DE PAGAMENTO",
                ]

        match tabulacao_upper:
            case  "PROMESSA":
                nome_pasta = "ACORDO"
            case "NAO NEGOCIO":
                nome_pasta = "NAO_NEGOCIO"
            case "DESCONHECIDO":
                nome_pasta = "DESCONHECIDO"
            case "LIGACAO CAIU":
                nome_pasta = "LIGACAO_CAIU"
            case "LIGACAO MUDA":
                nome_pasta = "LIGACAO MUDA"
            case "PAGAMENTO JÁ EFETUADO" | "PAGAMENTO JA EFETUADO":
                nome_pasta = "EFETUADO"

        match faixa_upper:
            case "COMERCIAL":
                faixa_selecionada_nome = "COMERCIAL"
            case "HABITACIONAL":
                faixa_selecionada_nome = "HABITACIONAL"
            case "PAGAMENTO":
                faixa_selecionada_nome = "PAGAMENTO"
            case "IMPRODUTIVAS" | "IMPRODUTIVA":
                faixa_selecionada_nome = "IMPRODUTIVAS"

        repo = SqlHvoiceRepository(
            dt_ligacao = self.data,
            dt_ligacao_final = self.data_final,
            grupo = self.faixa,
            tabulacao = self.tabulacao,
            duracao_min = self.min_minuto,
            duracao_max = self.max_minuto,
            cedente = self.cedente.upper(),
            qtd_operador = self.qtd_operador
        )

        print("Buscando dados no SQL...")

        dados_ligacoes = repo.coleta_dados_ligacoes_vega(
            dt_atraso = dt_atraso

        )
        print(f"Registros retornados do SQL: {len(dados_ligacoes)}")
        if not dados_ligacoes:
            print("Nenhum dado retornado da query SQL.")
            return None
        #print(dados_ligacoes)

        # Monta DataFrame
        df_metadados = repo.montando_metadados(dados_ligacoes=dados_ligacoes)
        print(f"DataFrame de metadados criado com {len(df_metadados)} linhas")

        # Localiza áudios
        resultado_audios = selecionado_audios_existentes(
            df_arquivo_metadados=df_metadados,
            valor_tempo = self.min_total_max
        )

        qtd_audios = len(resultado_audios["caminho_completo_audios_existentes"])
        print(f"Áudios encontrados: {qtd_audios}")

        if qtd_audios == 0:
            print("Nenhum áudio existente encontrado no servidor RBM.")

        # ================================
        # NOVO: Filtrar SOMENTE os índices com áudio
        # ================================

        # Garantir que o índice do DF está 0..N
        df_metadados = df_metadados.reset_index(drop=True)

        # Ajusta automaticamente e insere nome_audio corretamente
        df_filtrado = ajustando_metadados_ligacoes_existentes(
            metadados_ligacoes_existentes_df=resultado_audios,
            df_arquivo_metadados=df_metadados
        )

        # Remover coluna "[Call ID (Controle Interno)]" se existir (versão correta)
        df_filtrado = remover_colunas_call_id(df_filtrado)


        return self.gerar_arquivo_zip(
            faixa_selecionada_nome,
            nome_pasta,
            resultado_audios,
            df_filtrado
        )

    def metadados_cobranca(self):

        if isinstance(self.faixa, list):
            self.faixa = self.faixa[0] if self.faixa else ""
        if isinstance(self.tabulacao, list):
            self.tabulacao = self.tabulacao[0] if self.tabulacao else ""

        cedente_lower = self.cedente.strip().lower()

        if cedente_lower != "beta" and not self.faixa:
            raise ValueError("A faixa nao foi informada. Exemplo: 'FIXA', 'VARIAVEL', 'CARTAO', 'EMPRESTIMO' etc.")
        if not self.tabulacao:
            raise ValueError("A tabulacao nao foi informada. Exemplo: 'ACORDO', 'RECUSA', etc.")

        if cedente_lower == "beta":
            # BETA: quando nao informado, assume TODOS; quando informado, usa para filtro de produto.
            self.faixa = self.faixa.strip() if self.faixa else "TODOS"

        faixa_upper = self.faixa.strip().upper()
        tabulacao_upper = self.tabulacao.strip().upper()

        match cedente_lower:
            case "bancoalfa":
                tabela = "TB_HVOICE_ALFA_TESTE"
            case "delta":
                tabela = "TB_HVOICE_DELTA"
            case "beta":
                tabela = "METADADOS.TB_HVOICE_BETA_81"
            case _:
                raise ValueError(f"Cedente nao suportado para HVOICE: {self.cedente}")

        if cedente_lower == "bancoalfa":
            match tabulacao_upper:
                case "ACORDO":
                    self.tabulacao = ["ACORDO - FORMALIZADO"]
                case "RECUSA":
                    self.tabulacao = ["RECUSA DE PAGAMENTO"]

        elif cedente_lower == "delta" and faixa_upper == "EMPRESTIMO":
            match tabulacao_upper:
                case "RECUSA":
                    self.tabulacao = [
                        "RECUSA DE PAGAMENTO",
                        "SEM CODICOES DE PAGAMENTO",
                        "SEM CAPACIDADE DE PAGAMENTO",
                        "CLIENTE SEM INTERESSE"
                    ]
                case "ACORDO":
                    self.tabulacao = ["ACORDO - FORMALIZADO"]

        elif cedente_lower == "delta" and faixa_upper == "CONSIGNADO":
            match tabulacao_upper:
                case "RECUSA":
                    self.tabulacao = [
                        "RECUSA DE PAGAMENTO",
                        "SEM CODICOES DE PAGAMENTO",
                        "SEM CAPACIDADE DE PAGAMENTO",
                        "CLIENTE SEM INTERESSE"
                    ]
                case "ACORDO":
                    self.tabulacao = ["ACORDO - FORMALIZADO"]

        elif cedente_lower == "delta" and faixa_upper == "CARTAO":
            match tabulacao_upper:
                case "RECUSA":
                    self.tabulacao = [
                        "SEM CODICOES DE PAGAMENTO",
                        "SEM CAPACIDADE DE PAGAMENTO"
                    ]
                case "ACORDO":
                    self.tabulacao = ["ACORDO FORMALIZADO - CARTAO"]

        elif cedente_lower == "beta":
            match tabulacao_upper:
                case "RECUSA":
                    raise ValueError("Para BETA, use tabulacao 'NAO NEGOCIO' em vez de 'RECUSA'.")
                case "NAO NEGOCIO" | "NAO_NEGOCIO":
                    self.tabulacao = [
                        "SEM CONDICOES DE PAGAMENTO - ATRASO DE SALARIO",
                        "SEM CONDICOES DE PAGAMENTO - BEM FURTADO - ROUBADO",
                        "SEM CONDICOES DE PAGAMENTO - DATA DE VENCIMENTO NAO ATENDE",
                        "SEM CONDICOES DE PAGAMENTO - DEBITO EM OUTRAS INSTITUICOES",
                        "SEM CONDICOES DE PAGAMENTO - DESCONTROLE FINANCEIRO",
                        "SEM CONDICOES DE PAGAMENTO - DESEMPREGO",
                        "SEM CONDICOES DE PAGAMENTO - FINANCIOU PARA TERCEIROS",
                        "SEM CONDICOES DE PAGAMENTO - NAO MAPEADOS",
                        "SEM CONDICOES DE PAGAMENTO - REDUCAO DE RENDA",
                        "SEM CONDICOES DE PAGAMENTO - SAUDE",
                        "SEM INTERESSE EM LIQUIDAR",
                        "SEM INTERESSE EM PAGAR"
                    ]
                case "ACORDO":
                    self.tabulacao = [
                        "ACORDO QUITACAO",
                        "PAGAMENTO FATURA - INTERMEDIARIO",
                        "PAGAMENTO FATURA - MINIMO",
                        "PAGAMENTO FATURA - TOTAL",
                        "PARCELAMENTO DE FATURA",
                        "PROMESSA DE PAGAMENTO",
                        "PROMESSA DE PAGAMENTO A VISTA",
                        "PROMESSA DE PAGAMENTO APP",
                        "PROMESSA DE PAGAMENTO PARCELADO - COM ENTRADA"
                    ]

        match tabulacao_upper:
            case "NAO NEGOCIO" | "NAO_NEGOCIO":
                nome_pasta = "NAO_NEGOCIO"
            case "RECUSA":
                nome_pasta = "NAO_NEGOCIO"
            case "ACORDO":
                nome_pasta = "ACORDO"
            case _:
                nome_pasta = tabulacao_upper.replace(" ", "_")

        if cedente_lower == "beta":
            if faixa_upper in {"TODOS", "TODAS", "ALL", "*"}:
                faixa_selecionada_nome = "TODOS"
            elif "CARTAO" in faixa_upper:
                faixa_selecionada_nome = "CARTAO"
            elif any(chave in faixa_upper for chave in ("RENEG", "RENEGOCIACAO", "RENEGOCIAÇÃO")):
                faixa_selecionada_nome = "RENEG"
            elif "EMPRESTIMO" in faixa_upper:
                faixa_selecionada_nome = "EMPRESTIMO"
            else:
                faixa_selecionada_nome = faixa_upper.replace(" ", "_")
        else:
            match faixa_upper:
                case "CARTAO":
                    faixa_selecionada_nome = "CARTAO"
                case "EMPRESTIMO":
                    faixa_selecionada_nome = "EMPRESTIMO"
                case "FIXA":
                    faixa_selecionada_nome = "FIXA"
                case "VARIAVEL":
                    faixa_selecionada_nome = "VARIAVEL"
                case _:
                    faixa_selecionada_nome = faixa_upper.replace(" ", "_")

        repo = SqlHvoiceRepository(
            dt_ligacao=self.data,
            dt_ligacao_final=self.data_final,
            grupo=self.faixa,
            tabulacao=self.tabulacao,
            duracao_min=self.min_minuto,
            duracao_max=self.max_minuto,
            cedente=self.cedente.upper(),
            qtd_operador=self.qtd_operador
        )
        print("Buscando dados no SQL...")

        dados_ligacoes = repo.coleta_dados_ligacoes_geral(
            tabela=tabela
        )
        print(f"Registros retornados do SQL: {len(dados_ligacoes)}")
        if not dados_ligacoes:
            print("Nenhum dado retornado da query SQL.")
            return None

        df_metadados = SqlHvoiceRepository.montando_metadados_geral(dados_ligacoes=dados_ligacoes)
        print(f"DataFrame de metadados criado com {len(df_metadados)} linhas")

        resultado_audios = selecionado_audios_existentes_geral(
            df_arquivo_metadados=df_metadados,
            max_minuto_total=self.min_total_max,
            qtd_por_operador=self.qtd_operador
        )

        qtd_audios = len(resultado_audios["caminho_completo_audios_existentes"])
        print(f"Audios encontrados: {qtd_audios}")

        if qtd_audios == 0:
            print("Nenhum audio existente encontrado no servidor RBM.")

        df_metadados = df_metadados.reset_index(drop=True)

        df_filtrado = ajustando_metadados_ligacoes_existentes(
            metadados_ligacoes_existentes_df=resultado_audios,
            df_arquivo_metadados=df_metadados
        )

        df_filtrado = remover_colunas_call_id(df_filtrado)

        return self.gerar_arquivo_zip(
            faixa_selecionada_nome,
            nome_pasta,
            resultado_audios,
            df_filtrado
        )

    def gerar_arquivo_zip(self, faixa_selecionada_nome:str, nome_pasta:str, resultado_audios:dict, df_metadados:pd.DataFrame):
        # Diretórios
        dir_hvoice = diretorio_hvoice_publicado()
        os.makedirs(dir_hvoice, exist_ok=True)
        dir_hvoice_temp = diretorio_hvoice_local()
        os.makedirs(dir_hvoice_temp, exist_ok=True)


        nome_base = f"{self.cedente.upper()}_{faixa_selecionada_nome.upper()}_{nome_pasta.upper()}"

        # Diretório interno para organizar arquivos antes do zip
        diretorio_hvoice = os.path.join(dir_hvoice_temp, f"conteudo_temp_{uuid.uuid4().hex}")

        # Copia e converte áudios
        salvando_arquivo_audio(
            caminho_completo_audios_existentes=resultado_audios["caminho_completo_audios_existentes"],
            diretorio_raiz_hvoice=diretorio_hvoice,
            carteira=self.cedente,
            tipo_envio=self.faixa,
            data_hvoice=self.data,
            nome_pasta=nome_base,
            nome_audio_existente=resultado_audios["nome_audio_existente"]
        )

        # Salva CSV
        salvando_arquivo_metadado(
            df_arquivo_metadados=df_metadados,
            diretorio_raiz_hvoice=diretorio_hvoice,
            carteira=self.cedente,
            tipo_envio=self.faixa,
            data_hvoice=self.data,
            nome_pasta = nome_base
        )

        # Caminho final do arquivo ZIP
        total_segundos_audios = resultado_audios["total_segundos_audios"]
        periodo = self.data if self.data_final == self.data else f"{self.data}_a_{self.data_final}"
        zip_filename = f"{self.cedente.upper()}_{faixa_selecionada_nome}_{nome_pasta}_{periodo}_{total_segundos_audios}s.zip"
        zip_path = os.path.join(dir_hvoice, zip_filename)

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(diretorio_hvoice):
                for file in files:
                    zipf.write(os.path.join(root, file),
                            os.path.relpath(os.path.join(root, file), diretorio_hvoice))

        # Remove pasta temporária após compactar
        shutil.rmtree(diretorio_hvoice, ignore_errors=True)
        print(f" Pasta temporária removida: {diretorio_hvoice}")

        if not os.path.exists(zip_path):
            return None

        return {
            "zip_path": zip_path,
            "total_segundos_audios": resultado_audios["total_segundos_audios"],
            "total_minutos_audios": resultado_audios["total_minutos_audios"]
        }


def apagar_zip_apos_24h(zip_path: str):
    """
        Remove o arquivo ZIP e o diretório hvoice_envios após 1 hora.
    """
    def _apagar():
        try:
            # Remove o arquivo ZIP
            if os.path.exists(zip_path):
                os.remove(zip_path)
                print(f"ZIP removido automaticamente após 24h: {zip_path}")

        except Exception as e:
            print(f"Falha ao remover ZIP automaticamente: {e}")

    # Agenda exclusão para daqui 1 hora (3600 segundos)
    threading.Timer(86400, _apagar).start()
