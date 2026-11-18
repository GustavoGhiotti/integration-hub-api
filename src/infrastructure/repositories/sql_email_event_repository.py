import time
import random
import logging
import pyodbc
from src.shared.utils import env_load
from src.domain.repositories.email_event_repository import EmailEventRepository
from src.infrastructure.database.sql_server_connection import SQLServerConnection

log = logging.getLogger("sendgrid_sql")

# Tamanho explícito de cada parâmetro do INSERT na #tmp_eventos (mesma ordem das
# colunas). Sem isso, o pyodbc com fast_executemany "adivinha" o buffer ao gravar
# em tabela temporária e estoura com "String data, right truncation" quando um
# valor (ex.: MOTIVO/reason de bounce) é maior que o chute dele. Aqui forçamos o
# buffer no tamanho real de cada coluna. None = deixa o driver inferir (datas/int).
_TAMANHOS_INSERT_TEMP = [
    (pyodbc.SQL_VARCHAR, 100, 0),    # SG_EVENT_ID
    (pyodbc.SQL_VARCHAR, 50, 0),     # EVENTO
    (pyodbc.SQL_VARCHAR, 15, 0),     # CATEGORIA
    (pyodbc.SQL_VARCHAR, 320, 0),    # EMAIL
    (pyodbc.SQL_VARCHAR, 255, 0),    # MESSAGE_ID
    (pyodbc.SQL_VARCHAR, 100, 0),    # TEMPLATE_ID
    None,                            # DATA_EVENTO (datetime2)
    (pyodbc.SQL_WVARCHAR, 1000, 0),  # MOTIVO (nvarchar)
    (pyodbc.SQL_VARCHAR, 50, 0),     # STATUS_SMTP
    (pyodbc.SQL_VARCHAR, 20, 0),     # TIPO_BOUNCE
    (pyodbc.SQL_WVARCHAR, 2048, 0),  # URL (nvarchar)
    (pyodbc.SQL_WVARCHAR, 500, 0),   # USER_AGENT (nvarchar)
    (pyodbc.SQL_VARCHAR, 45, 0),     # IP
    None,                            # RAW_ID (int)
    (pyodbc.SQL_VARCHAR, 100, 0),    # ID_CEDENTE
]

# Ordem das colunas usada na gravação em lote dos eventos.
# O SendGridService.parse_evento devolve as tuplas EXATAMENTE nesta ordem.
COLUNAS_EVENTO = (
    "SG_EVENT_ID", "EVENTO", "CATEGORIA", "EMAIL", "MESSAGE_ID", "TEMPLATE_ID",
    "DATA_EVENTO", "MOTIVO", "STATUS_SMTP", "TIPO_BOUNCE", "URL", "USER_AGENT", "IP", "RAW_ID",
    "ID_CEDENTE",
)

# Tabela temporária (escopo da conexão) para o bulk insert antes do dedup/merge.
_SQL_CRIAR_TEMP = """
CREATE TABLE #tmp_eventos (
    SG_EVENT_ID varchar(100)   NULL,
    EVENTO      varchar(50)    NULL,
    CATEGORIA   varchar(15)    NULL,
    EMAIL       varchar(320)   NULL,
    MESSAGE_ID  varchar(255)   NULL,
    TEMPLATE_ID varchar(100)   NULL,
    DATA_EVENTO datetime2(3)   NULL,
    MOTIVO      nvarchar(1000) NULL,
    STATUS_SMTP varchar(50)    NULL,
    TIPO_BOUNCE varchar(20)    NULL,
    URL         nvarchar(2048) NULL,
    USER_AGENT  nvarchar(500)  NULL,
    IP          varchar(45)    NULL,
    RAW_ID      int            NULL,
    ID_CEDENTE  varchar(100)   NULL
);
"""

_SQL_INSERIR_TEMP = """
INSERT INTO #tmp_eventos
    (SG_EVENT_ID, EVENTO, CATEGORIA, EMAIL, MESSAGE_ID, TEMPLATE_ID, DATA_EVENTO,
     MOTIVO, STATUS_SMTP, TIPO_BOUNCE, URL, USER_AGENT, IP, RAW_ID, ID_CEDENTE)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
"""

# Insere na tabela granular só o que ainda não existe (dedup por SG_EVENT_ID),
# eliminando também duplicatas dentro do próprio lote.
_SQL_INSERIR_EVENTOS = """
INSERT INTO dbo.MONITOR_SENDGRID_EVENTOS
    (SG_EVENT_ID, EVENTO, CATEGORIA, EMAIL, MESSAGE_ID, TEMPLATE_ID, DATA_EVENTO,
     MOTIVO, STATUS_SMTP, TIPO_BOUNCE, URL, USER_AGENT, IP, RAW_ID, ID_CEDENTE)
SELECT t.SG_EVENT_ID, t.EVENTO, t.CATEGORIA, t.EMAIL, t.MESSAGE_ID, t.TEMPLATE_ID, t.DATA_EVENTO,
       t.MOTIVO, t.STATUS_SMTP, t.TIPO_BOUNCE, t.URL, t.USER_AGENT, t.IP, t.RAW_ID, t.ID_CEDENTE
FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY SG_EVENT_ID ORDER BY (SELECT 1)) AS rn
    FROM #tmp_eventos
) t
WHERE t.rn = 1
  AND NOT EXISTS (
      SELECT 1 FROM dbo.MONITOR_SENDGRID_EVENTOS e WHERE e.SG_EVENT_ID = t.SG_EVENT_ID
  );
"""

# Recalcula a tabela agregada SÓ para as chaves (EMAIL, MESSAGE_ID) reivindicadas
# pelo agregador (#lote), sempre a partir da tabela granular (deduplicada) ->
# idempotente e sempre correto.
_SQL_MERGE_AGREGADO = """
;WITH chaves AS (
    SELECT DISTINCT EMAIL, MESSAGE_ID FROM #lote WHERE MESSAGE_ID IS NOT NULL
),
agg AS (
    SELECT
        e.EMAIL, e.MESSAGE_ID,
        MAX(CASE WHEN e.EVENTO IN ('processed','delivered','deferred') THEN 1 ELSE 0 END) AS FOI_ENVIADO,
        MAX(CASE WHEN e.EVENTO = 'delivered' THEN 1 ELSE 0 END) AS FOI_ENTREGUE,
        MAX(CASE WHEN e.EVENTO = 'deferred'  THEN 1 ELSE 0 END) AS FOI_ADIADO,
        MAX(CASE WHEN e.EVENTO = 'open'  THEN 1 ELSE 0 END) AS FOI_ABERTO,
        MAX(CASE WHEN e.EVENTO = 'click' THEN 1 ELSE 0 END) AS FOI_CLICADO,
        MAX(CASE WHEN e.EVENTO = 'bounce' AND ISNULL(e.TIPO_BOUNCE,'') <> 'blocked' THEN 1 ELSE 0 END) AS FOI_BOUNCE,
        MAX(CASE WHEN e.EVENTO = 'bounce' AND e.TIPO_BOUNCE = 'blocked' THEN 1 ELSE 0 END) AS FOI_BLOQUEADO,
        MAX(CASE WHEN e.EVENTO = 'dropped' THEN 1 ELSE 0 END) AS FOI_DROPADO,
        MAX(CASE WHEN e.EVENTO = 'spamreport' THEN 1 ELSE 0 END) AS FOI_SPAM,
        MAX(CASE WHEN e.EVENTO IN ('bounce','dropped','spamreport') THEN 1 ELSE 0 END) AS EMAIL_INVALIDO,
        SUM(CASE WHEN e.EVENTO = 'open'  THEN 1 ELSE 0 END) AS QTD_ABERTURAS,
        SUM(CASE WHEN e.EVENTO = 'click' THEN 1 ELSE 0 END) AS QTD_CLIQUES,
        MAX(CASE WHEN e.EVENTO = 'processed' THEN e.DATA_EVENTO END) AS DATA_ULTIMO_ENVIO,
        MAX(CASE WHEN e.EVENTO = 'delivered' THEN e.DATA_EVENTO END) AS DATA_ULTIMA_ENTREGA,
        MIN(CASE WHEN e.EVENTO = 'open'  THEN e.DATA_EVENTO END) AS DATA_PRIMEIRA_ABERTURA,
        MAX(CASE WHEN e.EVENTO = 'open'  THEN e.DATA_EVENTO END) AS DATA_ULTIMA_ABERTURA,
        MIN(CASE WHEN e.EVENTO = 'click' THEN e.DATA_EVENTO END) AS DATA_PRIMEIRO_CLIQUE,
        MAX(CASE WHEN e.EVENTO = 'click' THEN e.DATA_EVENTO END) AS DATA_ULTIMO_CLIQUE,
        MAX(CASE WHEN e.EVENTO IN ('bounce','dropped') THEN e.DATA_EVENTO END) AS DATA_ULTIMA_FALHA,
        MAX(e.MOTIVO) AS MOTIVO_FALHA,
        MAX(e.TEMPLATE_ID) AS TEMPLATE_ID,
        MAX(e.ID_CEDENTE) AS ID_CEDENTE
    FROM dbo.MONITOR_SENDGRID_EVENTOS e
    INNER JOIN chaves c
        ON c.EMAIL = e.EMAIL
       AND c.MESSAGE_ID = e.MESSAGE_ID   -- igualdade pura (sargável) -> usa índice, sem scan
    GROUP BY e.EMAIL, e.MESSAGE_ID
)
MERGE dbo.MONITOR_SENDGRID AS tgt
USING agg AS src
   ON tgt.EMAIL = src.EMAIL
  AND tgt.MESSAGE_ID = src.MESSAGE_ID   -- igualdade pura -> seek no índice único (EMAIL, MESSAGE_ID), sem varrer os 7,4M
WHEN MATCHED THEN UPDATE SET
    FOI_ENVIADO            = src.FOI_ENVIADO,
    FOI_ENTREGUE           = src.FOI_ENTREGUE,
    FOI_ADIADO             = src.FOI_ADIADO,
    FOI_ABERTO             = src.FOI_ABERTO,
    FOI_CLICADO            = src.FOI_CLICADO,
    FOI_BOUNCE             = src.FOI_BOUNCE,
    FOI_BLOQUEADO          = src.FOI_BLOQUEADO,
    FOI_DROPADO            = src.FOI_DROPADO,
    FOI_SPAM               = src.FOI_SPAM,
    EMAIL_INVALIDO         = src.EMAIL_INVALIDO,
    QTD_ABERTURAS          = src.QTD_ABERTURAS,
    QTD_CLIQUES            = src.QTD_CLIQUES,
    DATA_ULTIMO_ENVIO      = src.DATA_ULTIMO_ENVIO,
    DATA_ULTIMA_ENTREGA    = src.DATA_ULTIMA_ENTREGA,
    DATA_PRIMEIRA_ABERTURA = src.DATA_PRIMEIRA_ABERTURA,
    DATA_ULTIMA_ABERTURA   = src.DATA_ULTIMA_ABERTURA,
    DATA_PRIMEIRO_CLIQUE   = src.DATA_PRIMEIRO_CLIQUE,
    DATA_ULTIMO_CLIQUE     = src.DATA_ULTIMO_CLIQUE,
    DATA_ULTIMA_FALHA      = src.DATA_ULTIMA_FALHA,
    MOTIVO_FALHA           = src.MOTIVO_FALHA,
    TEMPLATE_ID            = COALESCE(src.TEMPLATE_ID, tgt.TEMPLATE_ID),
    ID_CEDENTE             = COALESCE(src.ID_CEDENTE, tgt.ID_CEDENTE),
    DATA_ATUALIZACAO       = SYSUTCDATETIME()
WHEN NOT MATCHED THEN
    INSERT (EMAIL, MESSAGE_ID, FOI_ENVIADO, FOI_ENTREGUE, FOI_ADIADO, FOI_ABERTO, FOI_CLICADO,
            FOI_BOUNCE, FOI_BLOQUEADO, FOI_DROPADO, FOI_SPAM, EMAIL_INVALIDO,
            QTD_ABERTURAS, QTD_CLIQUES, DATA_ULTIMO_ENVIO, DATA_ULTIMA_ENTREGA,
            DATA_PRIMEIRA_ABERTURA, DATA_ULTIMA_ABERTURA, DATA_PRIMEIRO_CLIQUE, DATA_ULTIMO_CLIQUE,
            DATA_ULTIMA_FALHA, MOTIVO_FALHA, TEMPLATE_ID, ID_CEDENTE)
    VALUES (src.EMAIL, src.MESSAGE_ID, src.FOI_ENVIADO, src.FOI_ENTREGUE, src.FOI_ADIADO, src.FOI_ABERTO, src.FOI_CLICADO,
            src.FOI_BOUNCE, src.FOI_BLOQUEADO, src.FOI_DROPADO, src.FOI_SPAM, src.EMAIL_INVALIDO,
            src.QTD_ABERTURAS, src.QTD_CLIQUES, src.DATA_ULTIMO_ENVIO, src.DATA_ULTIMA_ENTREGA,
            src.DATA_PRIMEIRA_ABERTURA, src.DATA_ULTIMA_ABERTURA, src.DATA_PRIMEIRO_CLIQUE, src.DATA_ULTIMO_CLIQUE,
            src.DATA_ULTIMA_FALHA, src.MOTIVO_FALHA, src.TEMPLATE_ID, src.ID_CEDENTE);
"""

# Cria a #lote SEM parâmetro. CRÍTICO: comando sem parâmetro roda direto (não pelo
# sp_executesql), então a #lote nasce no escopo da SESSÃO e sobrevive aos próximos
# comandos. Se a #lote fosse criada junto de um INSERT parametrizado (SELECT TOP (?)),
# ela seria descartada ao fim do sp_executesql e o comando seguinte falharia com
# "Nome de objeto '#lote' inválido" (erro 208) — que era o bug que travava o agregador.
_SQL_CRIAR_LOTE = """
IF OBJECT_ID('tempdb..#lote') IS NOT NULL DROP TABLE #lote;
CREATE TABLE #lote (ID_EVENTO bigint PRIMARY KEY, EMAIL varchar(320), MESSAGE_ID varchar(255));
"""

# Reivindica um lote de eventos ainda não agregados (AGREGADO=0), FIFO por ID_EVENTO.
# READPAST/UPDLOCK deixa seguro mesmo se um dia rodar mais de um agregador.
# Parametrizado (TOP (?)): roda pelo sp_executesql, mas a #lote já existe na sessão,
# então o INSERT enxerga ela normalmente.
_SQL_INSERIR_LOTE = """
INSERT INTO #lote (ID_EVENTO, EMAIL, MESSAGE_ID)
SELECT TOP (?) ID_EVENTO, EMAIL, MESSAGE_ID
  FROM dbo.MONITOR_SENDGRID_EVENTOS WITH (READPAST, UPDLOCK, ROWLOCK)
 WHERE AGREGADO = 0
 ORDER BY ID_EVENTO;
"""

# Marca como agregados EXATAMENTE os eventos reivindicados (os que estão em #lote).
# Eventos novos que chegarem depois ficam AGREGADO=0 e entram no próximo ciclo.
_SQL_MARCAR_AGREGADO = """
UPDATE e
   SET AGREGADO = 1
  FROM dbo.MONITOR_SENDGRID_EVENTOS e
 INNER JOIN #lote l ON l.ID_EVENTO = e.ID_EVENTO;
"""


class SqlEmailEventRepository(EmailEventRepository):
    def __init__(self):
        self.db = SQLServerConnection(server=env_load.DB_66, database="DB_EMAIL")

    # ------------------------------------------------------------------ #
    #  Ingestão (rota /webhook) — precisa ser rápida                     #
    # ------------------------------------------------------------------ #
    def salvar_raw(self, headers: str, body: str):
        query = "INSERT INTO dbo.MONITOR_SENDGRID_RAW (HEADERS, BODY) VALUES (?, ?)"
        self.db.execute(query=query, parametros=(headers, body))

    # ------------------------------------------------------------------ #
    #  Consumidor em background                                          #
    # ------------------------------------------------------------------ #
    def reivindicar_lote(self, limite: int) -> list:
        """Reivindica (atomicamente) até `limite` linhas pendentes.
        Marca como PROCESSANDO (2) e incrementa TENTATIVAS.
        Retorna lista de tuplas (ID, BODY, TENTATIVAS)."""
        # READPAST + UPDLOCK + ROWLOCK: cada consumidor "pula" as linhas que outro
        # já travou, em vez de bloquear/deadlockar. Torna o claim seguro para
        # rodar VÁRIOS consumidores ao mesmo tempo.
        # ORDER BY ID: pega sempre as mais antigas primeiro (FIFO), para nenhuma
        # linha ficar esquecida enquanto o backlog não zera.
        query = """
            WITH cte AS (
                SELECT TOP (?) ID, BODY, PROCESSADO, TENTATIVAS
                  FROM dbo.MONITOR_SENDGRID_RAW WITH (READPAST, UPDLOCK, ROWLOCK)
                 WHERE PROCESSADO = 0
                 ORDER BY ID
            )
            UPDATE cte
               SET PROCESSADO = 2, TENTATIVAS = TENTATIVAS + 1
            OUTPUT inserted.ID, inserted.BODY, inserted.TENTATIVAS;
        """
        conexao = self.db._connect()
        try:
            cursor = conexao.cursor()
            cursor.execute(query, (limite,))
            linhas = [(r[0], r[1], r[2]) for r in cursor.fetchall()]
            conexao.commit()
            return linhas
        finally:
            try:
                conexao.close()
            except Exception:
                pass

    def gravar_detalhe(self, eventos: list):
        """Grava só o DETALHE (append-only): bulk insert em #temp -> insert com
        dedup na MONITOR_SENDGRID_EVENTOS. NÃO recalcula o resumo — isso é do
        agregador. Como é só INSERT (sem MERGE), vários consumidores rodam em
        paralelo praticamente sem contenção.

        Retry em deadlock (1205) e em chave duplicada (2627/2601), que pode ocorrer
        se dois consumidores receberem o mesmo evento repetido ao mesmo tempo."""
        if not eventos:
            return

        for tentativa in range(3):
            conexao = self.db._connect()
            try:
                cursor = conexao.cursor()
                cursor.fast_executemany = True

                cursor.execute(_SQL_CRIAR_TEMP)
                # Força o tamanho dos buffers (evita "String data, right truncation")
                cursor.setinputsizes(_TAMANHOS_INSERT_TEMP)
                cursor.executemany(_SQL_INSERIR_TEMP, eventos)
                cursor.execute(_SQL_INSERIR_EVENTOS)

                conexao.commit()
                return
            except Exception as e:
                try:
                    conexao.rollback()
                except Exception:
                    pass
                erro = str(e)
                transitorio = ("1205" in erro) or ("2627" in erro) or ("2601" in erro)
                if transitorio and tentativa < 2:
                    time.sleep(0.3 + random.random())
                    continue
                raise
            finally:
                try:
                    conexao.close()
                except Exception:
                    pass

    def agregar_lote(self, limite: int) -> int:
        """Recalcula o resumo (MONITOR_SENDGRID) para as chaves que têm eventos
        ainda não agregados. Roda em UM agregador só, então não briga com ninguém
        — é aqui que o MERGE (a parte pesada) fica isolada, fora dos consumidores.
        Retorna quantos eventos foram agregados neste ciclo (0 = nada a fazer)."""
        for tentativa in range(3):
            conexao = self.db._connect()
            try:
                cursor = conexao.cursor()

                cursor.execute(_SQL_CRIAR_LOTE)               # sem parâmetro -> #lote no escopo da sessão
                cursor.execute(_SQL_INSERIR_LOTE, (limite,))  # parametrizado; a #lote já existe
                cursor.execute("SELECT COUNT(*) FROM #lote;")
                total = cursor.fetchone()[0] or 0

                if total:
                    cursor.execute(_SQL_MERGE_AGREGADO)
                    cursor.execute(_SQL_MARCAR_AGREGADO)

                conexao.commit()
                return total
            except Exception as e:
                try:
                    conexao.rollback()
                except Exception:
                    pass
                if "1205" in str(e) and tentativa < 2:
                    time.sleep(0.5 + random.random())
                    continue
                raise
            finally:
                try:
                    conexao.close()
                except Exception:
                    pass

    def marcar_processados(self, ids: list):
        if not ids:
            return
        marcadores = ",".join("?" for _ in ids)
        query = f"""
            UPDATE dbo.MONITOR_SENDGRID_RAW
               SET PROCESSADO = 1, DATA_PROCESSAMENTO = SYSUTCDATETIME(), ERRO = NULL
             WHERE ID IN ({marcadores});
        """
        self.db.execute(query=query, parametros=tuple(ids))

    def marcar_falha(self, ids: list, erro: str | None = None):
        """Falha transitória (ex.: banco). Devolve para a fila (0) até o limite
        de 5 tentativas; a partir daí marca como erro definitivo (9)."""
        if not ids:
            return
        marcadores = ",".join("?" for _ in ids)
        query = f"""
            UPDATE dbo.MONITOR_SENDGRID_RAW
               SET PROCESSADO = CASE WHEN TENTATIVAS >= 5 THEN 9 ELSE 0 END,
                   DATA_PROCESSAMENTO = CASE WHEN TENTATIVAS >= 5 THEN SYSUTCDATETIME() ELSE DATA_PROCESSAMENTO END,
                   ERRO = ?
             WHERE ID IN ({marcadores});
        """
        self.db.execute(query=query, parametros=(erro, *ids))

    def marcar_erro_parse(self, ids: list, motivo: str):
        """Corpo inválido (JSON quebrado): nunca vai processar -> erro definitivo (9)."""
        if not ids:
            return
        marcadores = ",".join("?" for _ in ids)
        query = f"""
            UPDATE dbo.MONITOR_SENDGRID_RAW
               SET PROCESSADO = 9, DATA_PROCESSAMENTO = SYSUTCDATETIME(), ERRO = ?
             WHERE ID IN ({marcadores});
        """
        self.db.execute(query=query, parametros=(motivo, *ids))

    # ------------------------------------------------------------------ #
    #  Manutenção                                                        #
    # ------------------------------------------------------------------ #
    def resetar_processando(self) -> int:
        """No startup: devolve para a fila linhas que ficaram presas em
        PROCESSANDO (2) por causa de um encerramento no meio do lote."""
        query = """
            UPDATE dbo.MONITOR_SENDGRID_RAW
               SET PROCESSADO = CASE WHEN TENTATIVAS >= 5 THEN 9 ELSE 0 END
             WHERE PROCESSADO = 2;
        """
        return self.db.execute(query=query, parametros=()) or 0

    def limpar_raw_antigo(self, dias: int) -> int:
        """Remove da RAW as linhas já processadas com mais de `dias` dias."""
        query = """
            DELETE TOP (5000) FROM dbo.MONITOR_SENDGRID_RAW
             WHERE PROCESSADO IN (1, 9)
               AND DATA_PROCESSAMENTO IS NOT NULL
               AND DATA_PROCESSAMENTO < DATEADD(DAY, -?, SYSUTCDATETIME());
        """
        total = 0
        conexao = self.db._connect()
        try:
            cursor = conexao.cursor()
            while True:
                cursor.execute(query, (dias,))
                afetadas = cursor.rowcount
                conexao.commit()
                total += afetadas if afetadas and afetadas > 0 else 0
                if not afetadas or afetadas < 5000:
                    break
            return total
        finally:
            try:
                conexao.close()
            except Exception:
                pass

    def metricas_saude(self) -> dict:
        # Consultas LEVES (NOLOCK + índices): contagens por PROCESSADO usam o
        # IX_MSR_PROCESSADO, o último processamento usa o IX_MSR_LIMPEZA e os
        # eventos não agregados usam o índice filtrado IX_MSE_AGREGADO. Nada de
        # varrer a tabela inteira -> o /health responde rápido mesmo com a RAW grande.
        query = """
            SELECT
                (SELECT COUNT(*) FROM dbo.MONITOR_SENDGRID_RAW WITH (NOLOCK) WHERE PROCESSADO = 0) AS pendentes,
                (SELECT COUNT(*) FROM dbo.MONITOR_SENDGRID_RAW WITH (NOLOCK) WHERE PROCESSADO = 2) AS processando,
                (SELECT COUNT(*) FROM dbo.MONITOR_SENDGRID_RAW WITH (NOLOCK) WHERE PROCESSADO = 9) AS erros,
                (SELECT MAX(DATA_PROCESSAMENTO) FROM dbo.MONITOR_SENDGRID_RAW WITH (NOLOCK) WHERE PROCESSADO = 1) AS ultimo_processamento,
                (SELECT COUNT(*) FROM dbo.MONITOR_SENDGRID_EVENTOS WITH (NOLOCK) WHERE AGREGADO = 0) AS eventos_nao_agregados;
        """
        linhas = self.db.execute(query=query, parametros=(), fetch=True)
        return linhas[0] if linhas else {}
