from src.infrastructure.database.sql_server_connection import SQLServerConnection
from src.shared.utils.env_load import DB_66


class ControleEnviosRepository:
    def __init__(self):
        self.db = SQLServerConnection(server=DB_66, database="DB_CHATBOT")

    def _obter_colunas_tabela(self, schema: str, tabela: str) -> set[str]:
        query = """
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS WITH (NOLOCK)
            WHERE TABLE_SCHEMA = ?
              AND TABLE_NAME = ?
        """
        rows = self.db.execute(query=query, parametros=(schema, tabela), fetch=True) or []
        return {str(row["COLUMN_NAME"]).upper() for row in rows}

    def obter_contagens_do_dia(self, provedor: str, numeros: list[str]) -> dict[str, int]:
        if not numeros:
            return {}

        placeholders = ", ".join("?" for _ in numeros)
        query = f"""
            SELECT
                NUMERO,
                COUNT(*) AS QTD_ENVIOS
            FROM dbo.TB_CONTROLE_ENVIOS_NUMERO WITH (NOLOCK)
            WHERE PROVEDOR = ?
              AND DATA_REFERENCIA = CAST(GETDATE() AS DATE)
              AND NUMERO IN ({placeholders})
            GROUP BY NUMERO
        """

        parametros = (provedor, *numeros)
        rows = self.db.execute(query=query, parametros=parametros, fetch=True) or []
        return {row["NUMERO"]: int(row.get("QTD_ENVIOS") or 0) for row in rows}

    def registrar_envio(
        self,
        provedor: str,
        numero: str,
        *,
        numero_destino: str | None = None,
        id_cedente: int | None = None,
        id_cedente_normalizado: int | None = None,
        canal: str | None = None,
        id_usuario_solicitante: int | None = None,
        usuario_solicitante: str | None = None,
        template: str | None = None,
        message_id: str | None = None,
    ):
        colunas = self._obter_colunas_tabela("dbo", "TB_CONTROLE_ENVIOS_NUMERO")
        colunas_base = [
            "PROVEDOR",
            "NUMERO",
            "DATA_REFERENCIA",
            "QTD_ENVIOS",
            "DT_ATUALIZACAO",
        ]
        valores_base = [
            "?",
            "?",
            "CAST(GETDATE() AS DATE)",
            "1",
            "GETDATE()",
        ]
        parametros = [provedor, numero]

        colunas_opcionais = [
            ("NUMERO_DESTINO", numero_destino),
            ("ID_CEDENTE", id_cedente),
            ("ID_CEDENTE_NORMALIZADO", id_cedente_normalizado),
            ("CANAL", canal),
            ("ID_USUARIO_SOLICITANTE", id_usuario_solicitante),
            ("USUARIO_SOLICITANTE", usuario_solicitante),
            ("TEMPLATE", template),
            ("MESSAGE_ID", message_id),
        ]
        colunas_presentes = [
            (coluna, valor)
            for coluna, valor in colunas_opcionais
            if coluna in colunas
        ]

        for coluna, valor in colunas_presentes:
            colunas_base.append(coluna)
            valores_base.append("?")
            parametros.append(valor)

        query_insert = f"""
            INSERT INTO dbo.TB_CONTROLE_ENVIOS_NUMERO (
                {", ".join(colunas_base)}
            )
            VALUES (
                {", ".join(valores_base)}
            );
        """

        self.db.execute(query=query_insert, parametros=tuple(parametros))

        query_update = """
            UPDATE dbo.TB_CONTROLE_ENVIOS_NUMERO
            SET
                QTD_ENVIOS = contagem.total_envios,
                DT_ATUALIZACAO = GETDATE()
            FROM dbo.TB_CONTROLE_ENVIOS_NUMERO historico
            CROSS APPLY (
                SELECT COUNT(*) AS total_envios
                FROM dbo.TB_CONTROLE_ENVIOS_NUMERO contagem WITH (NOLOCK)
                WHERE contagem.PROVEDOR = historico.PROVEDOR
                  AND contagem.NUMERO = historico.NUMERO
                  AND contagem.DATA_REFERENCIA = historico.DATA_REFERENCIA
            ) contagem
            WHERE historico.PROVEDOR = ?
              AND historico.NUMERO = ?
              AND historico.DATA_REFERENCIA = CAST(GETDATE() AS DATE);
        """

        self.db.execute(query=query_update, parametros=(provedor, numero))
