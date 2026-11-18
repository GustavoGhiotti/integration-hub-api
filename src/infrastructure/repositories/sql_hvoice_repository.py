from src.infrastructure.database.sql_server_connection import SQLServerConnection
from src.shared.utils.env_load import *
import pyodbc 
import pandas as pd
from datetime import datetime
import re


class SqlHvoiceRepository:
    def __init__(self, dt_ligacao: str, grupo: str, 
                 tabulacao: list[str] | str, duracao_min: int , duracao_max: int, cedente: str, qtd_operador:int,
                 dt_ligacao_final: str | None = None):
        self.dt_ligacao = self._normalizar_data(dt_ligacao)
        self.dt_ligacao_final = self._normalizar_data(dt_ligacao_final or dt_ligacao)
        self.duracao_min = duracao_min
        self.duracao_max = duracao_max
        self.grupo = grupo
        self.tabulacao = tabulacao  
        self.cedente = cedente
        self.qtd_operador = qtd_operador


        MAPEAMENTO_BANCOS = {
            "vega": (DB_248, "DB_PROC_ACME"),
            "bancoalfa": (DB_71, "DB_REPORT"),
            "delta": (DB_71, "DB_REPORT"),
            "beta": (DB_72, "DB_DADOS")
        }

        server, database = MAPEAMENTO_BANCOS.get(
            self.cedente.strip().lower(),
            (DB_71, "DB_REPORT")  # padrão caso não encontre
        )

        self.db = SQLServerConnection(server=server, database=database)

    @staticmethod
    def _normalizar_data(valor: str) -> str:
        for formato in ("%Y-%m-%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(str(valor), formato).strftime("%Y-%m-%d")
            except ValueError:
                continue
        print(f"Formato de data invalido: {valor}")
        return str(valor)

    def coleta_dados_ligacoes_geral(self, tabela: str):
            
            if isinstance(self.tabulacao, str):
                tabulacoes = [self.tabulacao.strip()]
            else:
                tabulacoes = [t.strip() for t in self.tabulacao if t]

            ignora_grupo = (
                self.cedente.strip().lower() == "beta"
                or not self.grupo
                or str(self.grupo).strip().upper() in {"TODOS", "TODAS", "ALL", "*"}
            )

            if ignora_grupo:
                filtro_grupo = ""
                parametros_grupo = ()
            else:
                filtro_grupo = "AND GRUPO = ?"
                parametros_grupo = (self.grupo,)

            filtro_produto_beta = ""
            parametros_produto_beta = ()
            if self.cedente.strip().lower() == "beta":
                produto_beta = str(self.grupo).strip().upper() if self.grupo else "TODOS"
                if produto_beta in {"TODOS", "TODAS", "ALL", "*"}:
                    filtro_produto_beta = ""
                    parametros_produto_beta = ()
                elif "CARTAO" in produto_beta:
                    filtro_produto_beta = "AND [Nome do Produto (Controle Interno)] LIKE ?"
                    parametros_produto_beta = ("%CARTAO%",)
                elif "EMPRESTIMO" in produto_beta:
                    filtro_produto_beta = "AND [Nome do Produto (Controle Interno)] LIKE ?"
                    parametros_produto_beta = ("%EMPRESTIMO%",)
                elif any(chave in produto_beta for chave in ("RENEG", "RENEGOCIACAO", "RENEGOCIAÇÃO")):
                    filtro_produto_beta = "AND [Nome do Produto (Controle Interno)] LIKE ?"
                    parametros_produto_beta = ("%RENEG%",)
                else:
                    filtro_produto_beta = "AND [Nome do Produto (Controle Interno)] LIKE ?"
                    parametros_produto_beta = (f"%{produto_beta}%",)

            parametros_base = (self.dt_ligacao, self.dt_ligacao_final, *parametros_grupo, *parametros_produto_beta)

            # A quantidade por operador so pode ser aplicada depois de validar
            # que o arquivo de audio existe. Os demais casos sao os fallbacks.
            #
            # Delta "acordo": ja existe mais de uma variacao da tabulacao de
            # acordo (ex.: "ACORDO - FORMALIZADO", "ACORDO FORMALIZADO - CARTAO"
            # e novas variantes). Para capturar todas, usamos LIKE '%ACORDO%' em
            # vez de igualdade exata. Os demais casos (RECUSA, outros cedentes)
            # continuam com igualdade exata.
            usar_like_acordo = (
                self.cedente.strip().lower() == "delta"
                and bool(tabulacoes)
                and all("ACORDO" in t.upper() for t in tabulacoes)
            )

            if usar_like_acordo:
                filtro_tabulacao_sql = "[TABULAÇÃO (CONTROLE INTERNO)] LIKE ?"
                parametros = (*parametros_base, "%ACORDO%", self.duracao_min, self.duracao_max)
            elif len(tabulacoes) == 1:
                filtro_tabulacao_sql = "[TABULAÇÃO (CONTROLE INTERNO)] = ?"
                parametros = (*parametros_base, tabulacoes[0], self.duracao_min, self.duracao_max)
            else:
                placeholders = ", ".join("?" for _ in tabulacoes)
                filtro_tabulacao_sql = f"[TABULAÇÃO (CONTROLE INTERNO)] IN ({placeholders})"
                parametros = (*parametros_base, *tabulacoes, self.duracao_min, self.duracao_max)

            query = f'''
                            SELECT 
                                [ID do Operador],
                                [ID do Acionamento],
                                [CPF/CNPJ do Cliente],
                                CONVERT(VARCHAR(19), [Data Hora do Acionamento], 120) AS [Data Hora do Acionamento],
                                [DURACAO_DO_ACIONAMENTO],
                                [Número do Contrato], 
                                [Códigos de Ação e Resultado Informado],
                                [Nome do Operador (Controle Interno)], 
                                [Supervisor (Controle Interno)],
                                [CALL ID (CONTROLE INTERNO)],
                                [CALL ID TAB(CONTROLE INTERNO)],
                                [Tabulação (Controle Interno)],
                                [Subtabulação (Controle Interno)],
                                [Código do Produto (Controle Interno)],    
                                [Nome do Produto (Controle Interno)]

                            FROM {tabela} WITH (NOLOCK)
                            WHERE DT_LIGACAO BETWEEN ? AND ?
                            {filtro_grupo}
                            {filtro_produto_beta}
                            AND {filtro_tabulacao_sql}
                            AND DURACAO_DO_ACIONAMENTO BETWEEN ? AND ?
                            ORDER BY [ID do Operador],
                                     [Data Hora do Acionamento] DESC,
                                     [ID do Acionamento] DESC
                    '''

            # return self.db.execute(query=query, parametros=parametros, fetch=True)
            dados = self.db.execute(query=query, parametros=parametros, fetch=True)
            return dados
    
    _COL_ALIASES_GERAL = {
        '[id do operador]': ['id do operador', '[id do operador]'],
        '[id do acionamento]': ['id do acionamento', '[id do acionamento]'],
        '[cpf/cnpj do cliente]': ['cpf/cnpj do cliente', '[cpf/cnpj do cliente]'],
        '[data hora do acionamento]': ['data hora do acionamento', '[data hora do acionamento]'],
        '[duração do acionamento]': ['duração do acionamento', 'duracao do acionamento', '[duração do acionamento]'],
        '[número do contrato]': ['número do contrato', 'numero do contrato', '[número do contrato]'],
        '[códigos de ação e resultado informado]': [
            'códigos de ação e resultado informado',
            'codigos de ação e resultado informado',
            'codigos de acao e resultado informado',
            '[códigos de ação e resultado informado]'
        ],
        '[nome do operador (controle interno)]': ['nome do operador (controle interno)', '[nome do operador (controle interno)]'],
        '[supervisor (controle interno)]': ['supervisor (controle interno)', '[supervisor (controle interno)]'],
        '[call id (controle interno)]': ['call id (controle interno)', '[call id (controle interno)]'],
        '[call id tab(controle interno)]': ['call id tab(controle interno)', '[call id tab(controle interno)]'],
        '[tabulação (controle interno)]': ['tabulação (controle interno)', 'tabulacao (controle interno)', '[tabulação (controle interno)]'],
        '[subtabulação (controle interno)]': ['subtabulação (controle interno)', 'subtabulacao (controle interno)', '[subtabulação (controle interno)]'],
        '[código do produto (controle interno)]': ['código do produto (controle interno)', 'codigo do produto (controle interno)', '[código do produto (controle interno)]'],
        '[nome do produto (controle interno)]': ['nome do produto (controle interno)', '[nome do produto (controle interno)]']
    }

    _COLUNAS_FINAIS = [
        '[ID do Operador]',
        '[ID do Acionamento]',
        '[CPF/CNPJ do Cliente]',
        '[Data Hora do Acionamento]',
        '[Duração do Acionamento]',
        '[Número do Contrato]',
        '[Códigos de Ação e Resultado Informado]',
        '[Nome do Operador (Controle Interno)]',
        '[Supervisor (Controle Interno)]',
        '[CALL ID (CONTROLE INTERNO)]',
        '[CALL ID TAB(CONTROLE INTERNO)]',
        '[Tabulação (Controle Interno)]',
        '[Subtabulação (Controle Interno)]',
        '[Código do Produto (Controle Interno)]',
        '[Nome do Produto (Controle Interno)]',
    ]

    @staticmethod
    def _norm_key_geral(s: str) -> str:
        """Normaliza nomes de colunas (remove colchetes, espaços e deixa minúsculo)."""
        return re.sub(r'[\[\]]', '', s).strip().lower()


    @staticmethod
    def montando_metadados_geral(dados_ligacoes: list) -> pd.DataFrame:
        if not dados_ligacoes:
            return pd.DataFrame()

        df = pd.DataFrame(dados_ligacoes)

        df.columns = [c.strip() for c in df.columns]

        df.columns = [f"[{col}]" if not col.startswith("[") else col for col in df.columns]

        for col in df.columns:
            if "duracao" in col.lower().replace("ç", "c"):
                df.rename(columns={col: "[Duração do Acionamento]"}, inplace=True)

        return df
    
    def coleta_dados_ligacoes_vega(self, dt_atraso:int):

        try:
            self.dt_ligacao = datetime.strptime(self.dt_ligacao, "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            try:
                self.dt_ligacao = datetime.strptime(self.dt_ligacao, "%Y/%m/%d").strftime("%Y-%m-%d")
            except ValueError:
                print(f"Formato de data inválido: {self.dt_ligacao}")

        # ===============================================================
        # TRATAMENTO DE TABULAÇÃO
        # ===============================================================
        if isinstance(self.tabulacao, str):
            tabulacoes = [self.tabulacao.strip()]
        else:
            tabulacoes = [t.strip() for t in self.tabulacao if t]
        
        tab_upper = [t.upper() for t in tabulacoes]

        # ========================
        # NORMALIZA GRUPO (FAIXA) -> lista de strings
        # ========================
        if isinstance(self.grupo, (list, tuple, set)):
            grupos = [str(g).strip() for g in self.grupo if g]
        else:
            grupos = [str(self.grupo).strip()] if self.grupo else []

        if not grupos:
            raise ValueError("Campo 'grupo' (faixa) não pode ser vazio.")

        grupos_upper = [g.upper() for g in grupos]

        # ===============================================================
        # DEFINIR FILTRO DO MAILING (caso improdutiva = traz todos)
        # ===============================================================
        if "IMPRODUTIVAS" in grupos_upper:
            # todos os mailings
            condicao_mailing = "[Nome do Mailing (Controle Interno)] LIKE ?"
            mailing_params = ("%",)

        elif any("PAGAMENTO JA EFETUADO" in t or "PAGAMENTO JÁ EFETUADO" in t for t in tab_upper):
            # limitar HAB/COMER (escapando "_" no LIKE)
            condicao_mailing = (
                "([Nome do Mailing (Controle Interno)] LIKE ? ESCAPE '\\' "
                "OR [Nome do Mailing (Controle Interno)] LIKE ? ESCAPE '\\')"
            )
            mailing_params = ("%[_]HABIT[_]FASES%", "%[_]COMER[_]FASES%")
        else:
            # filtro normal por grupo
            condicao_mailing = "[Nome do Mailing (Controle Interno)] LIKE ?"
            mailing_params = (f"%{self.grupo}%",)
        # ===============================================================
        # ESCOLHER CAMPO DE TABULAÇÃO
        # (se for “ligação muda / ligação caiu” → tabulação principal)
        # ===============================================================
        termos_excecao = ["LIGACAO MUDA", "LIGAÇÃO MUDA", "LIGACAO CAIU", "LIGAÇÃO CAIU"]
        tab_upper = [t.upper() for t in tabulacoes]

        # Verifica se ALGUMA tabulação contém ALGUM dos termos de exceção
        if any(exc in t for t in tab_upper for exc in termos_excecao):
            campo_tabulacao = "[Tabulação (Controle Interno)]"
        else:
            campo_tabulacao = "[Subtabulação (Controle Interno)]"

        # ===============================================================
        # DEFINIR FILTRO DE TABULAÇÃO
        # ===============================================================
        if len(tabulacoes) == 1:
            filtro_tabulacao = "LIKE ?"
            parametros = (self.dt_ligacao, self.dt_ligacao_final, int(dt_atraso), *mailing_params, f"%{tabulacoes[0]}%", self.duracao_min, self.duracao_max, self.qtd_operador)
        else:
            placeholders = ", ".join("?" for _ in tabulacoes)
            filtro_tabulacao = f"IN ({placeholders})"
            parametros = (self.dt_ligacao, self.dt_ligacao_final, int(dt_atraso), *mailing_params, *tabulacoes, self.duracao_min, self.duracao_max, self.qtd_operador)

        query = f'''
            WITH CTE AS (
                SELECT [Call ID (Controle Interno)]
                    ,COUNT(*) AS QTD
                FROM [DB_PROC_ACME].[dbo].[TBL_MONITORIA_HVOICE] WITH (NOLOCK)
                GROUP BY [Call ID (Controle Interno)]
                HAVING COUNT(*) = 1
            ),
            Base AS (
                SELECT 
                    [ID do Operador],
                    [ID do Acionamento],
                    [CPF/CNPJ do Cliente],
                    CONVERT(VARCHAR(23), [Data Hora do Acionamento], 121) AS [Data Hora do Acionamento],
                    [Duração do Acionamento],
                    [Número do Contrato], 
                    [Códigos de Ação e Resultado Informado],
                    [Nome do Operador (Controle Interno)], 
                    [Supervisor (Controle Interno)],
                    [Call ID (Controle Interno)],
                    [Tabulação (Controle Interno)],
                    [Subtabulação (Controle Interno)],
                    [Código do Produto (Controle Interno)],	
                    [Nome do Produto (Controle Interno)],

                    ROW_NUMBER() OVER (
                        PARTITION BY [ID do Operador]
                        ORDER BY [Data Hora do Acionamento] DESC
                    ) AS rn

                FROM TBL_MONITORIA_HVOICE WITH (NOLOCK)
                WHERE CAST([Data Hora do Acionamento] AS DATE) BETWEEN ? AND ?
                AND DIAS_ATRASO < ?
                AND {condicao_mailing}
                AND {campo_tabulacao} {filtro_tabulacao}
                AND [Duração do Acionamento] BETWEEN ? AND ?
                AND [Marca (Controle Interno)] = '00000'
            )

            SELECT
                [ID do Operador],
                [ID do Acionamento],
                [CPF/CNPJ do Cliente],
                [Data Hora do Acionamento],
                [Duração do Acionamento],
                [Número do Contrato], 
                [Códigos de Ação e Resultado Informado],
                [Nome do Operador (Controle Interno)], 
                [Supervisor (Controle Interno)],
                [Call ID (Controle Interno)],
                [Tabulação (Controle Interno)],
                [Subtabulação (Controle Interno)],
                [Código do Produto (Controle Interno)],	
                [Nome do Produto (Controle Interno)]	
            FROM Base
            WHERE rn <= ?
            ORDER BY [ID do Operador], [Data Hora do Acionamento] DESC;
        '''

        return self.db.execute(query=query, parametros=parametros, fetch=True)

    def _norm_key(self, s: str) -> str:
        return re.sub(r'[\[\]]', '', s).strip().lower()

    # mapeamento de nomes-alvo (sem colchetes) -> lista de aliases aceitos
    _COL_ALIASES = {
        'id do operador': ['id do operador'],
        'id do acionamento': ['id do acionamento'],
        'cpf/cnpj do cliente': ['cpf/cnpj do cliente'],
        'data hora do acionamento': ['data hora do acionamento'],
        'duração do acionamento': ['duração do acionamento', 'duracao do acionamento'],
        'número do contrato': ['número do contrato', 'numero do contrato'],
        'códigos de ação e resultado informado': ['códigos de ação e resultado informado','codigos de ação e resultado informado','codigos de acao e resultado informado'],
        'nome do operador (controle interno)': ['nome do operador (controle interno)'],
        'supervisor (controle interno)': ['supervisor (controle interno)'],
        'call id (controle interno)': ['call id (controle interno)', 'call id (controle interno)'],
        'call id tab(controle interno)': ['call id tab(controle interno)'],
        'tabulação (controle interno)': ['tabulação (controle interno)','tabulacao (controle interno)'],
        'subtabulação (controle interno)': ['subtabulação (controle interno)','subtabulacao (controle interno)'],
        'código do produto (controle interno)': ['código do produto (controle interno)','codigo do produto (controle interno)'],
        'nome do produto (controle interno)': ['nome do produto (controle interno)'],
    }

    # ordem/nomes finais das colunas no DataFrame (sem colchetes)
    _COLUNAS_FINAIS = [
        '[ID do Operador]',
        '[ID do Acionamento]',
        '[CPF/CNPJ do Cliente]',
        '[Data Hora do Acionamento]',
        '[Duração do Acionamento]',
        '[Número do Contrato]',
        '[Códigos de Ação e Resultado Informado]',
        '[Nome do Operador (Controle Interno)]',
        '[Supervisor (Controle Interno)]',
        '[CALL ID (CONTROLE INTERNO)]',
        '[CALL ID TAB(CONTROLE INTERNO)]',
        '[Tabulação (Controle Interno)]',
        '[Subtabulação (Controle Interno)]',
        '[Código do Produto (Controle Interno)]',
        '[Nome do Produto (Controle Interno)]',
    ]

    def montando_metadados(self, dados_ligacoes: list) -> pd.DataFrame:
        if not dados_ligacoes:
            return pd.DataFrame(columns=self._COLUNAS_FINAIS)

        exemplo = dados_ligacoes[0]
        if isinstance(exemplo, dict):
            sample_keys = list(exemplo.keys())
        elif isinstance(exemplo, pyodbc.Row):
            sample_keys = [d[0] for d in exemplo.cursor_description]
        elif isinstance(exemplo, (tuple, list)):
            sample_keys = []
        else:
            sample_keys = []

        norm_map = { self._norm_key(k): k for k in sample_keys }

        linhas = []
        for linha in dados_ligacoes:
            if isinstance(linha, dict):
                base = { self._norm_key(k): v for k, v in linha.items() }
            elif isinstance(linha, pyodbc.Row):
                base = {}
                for i, alvo in enumerate(self._COLUNAS_FINAIS):
                    try:
                        base[alvo] = linha[i]
                    except Exception:
                        pass
            elif isinstance(linha, (tuple, list)):
                base = {}
                for i, alvo in enumerate(self._COLUNAS_FINAIS[:len(linha)]):
                    base[alvo] = linha[i]
            else:
                continue

            out = {}
            for alvo in self._COLUNAS_FINAIS:
                val = None
                for alias in self._COL_ALIASES[self._norm_key(alvo)]:
                    key_norm = self._norm_key(alias)
                    if key_norm in base:
                        val = base[key_norm]
                        break
                    if key_norm in norm_map and norm_map[key_norm] in base:
                        val = base[norm_map[key_norm]]
                        break

                if alvo == 'data hora do acionamento':
                    if val is None:
                        out[alvo] = None
                    elif hasattr(val, 'strftime'):
                        out[alvo] = val.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        s = str(val).strip()
                        if '.' in s and len(s.split(' ')) == 2:
                            s = s.split('.')[0]
                        out[alvo] = s
                else:
                    out[alvo] = val
            linhas.append(out)

        df = pd.DataFrame(linhas, columns=self._COLUNAS_FINAIS)
        return df
