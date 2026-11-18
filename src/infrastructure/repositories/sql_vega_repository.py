from src.infrastructure.database.sql_server_connection import SQLServerConnection
from src.shared.utils import env_load


class VegaRepository:
    def __init__(self):
        self.db_proc = SQLServerConnection(
            server=env_load.DB_248,
            database="DB_PROC"
        )

        self.db_easy = SQLServerConnection(
            server=env_load.DB_170,
            database="easycollector"
        )

    def buscar_cpf_por_id_cliente(self, id_cliente: int):
        query = """
            SELECT NR_CPF
            FROM TBL_CLIENTE WITH(NOLOCK)
            WHERE ID_CLIENTE = ?
        """
        return self.db_proc.execute(
            query=query,
            parametros=(id_cliente,),
            fetch=True
        )

    def buscar_dados_cliente(self, cpf: str):
        query = """
            SELECT 
                A.NR_CPF,
                A.ID_CLIENTE,
                B.NM_CLIENTE,
                A.TP_CONTRATO,
                A.VL_PRESTACAO,
                A.DIAS_ATRASO,
                A.FASE,
                A.NR_CONTRATO,
                CONVERT(VARCHAR, GETDATE() + 6, 105) AS DIA_VENCIMENTO,
                A.NM_PRODUTO,
                A.PARCELA_ATRASO,
                A.NM_GRUPO_PRODUTO
            FROM dbo.FN_CONSULTA_CLIENTE_VEGA_V2(?) AS A
            INNER JOIN TBL_CLIENTE AS B ON A.ID_CLIENTE = B.ID_CLIENTE
        """

        return self.db_proc.execute(
            query=query,
            parametros=(cpf,),
            fetch=True
        )

    def buscar_email_cliente(self, id_cliente: str):
        query = """
            SELECT TOP 1 NM_EMAIL
            FROM TB_CLIENTE_EMAIL WITH(NOLOCK)
            WHERE ID_CLIENTE = ?
              AND TP_PREFERENCIAL = 1
        """

        return self.db_easy.execute(
            query=query,
            parametros=(id_cliente,),
            fetch=True
        )
