from __future__ import annotations

from datetime import datetime
from typing import Any

from src.infrastructure.database.sql_server_connection import SQLServerConnection


class EasycollectorCargaRepository:
    def __init__(self, server: str = "10.0.0.65") -> None:
        self._db = SQLServerConnection(server=server, database="easycollector")

    def listar_por_data(self, data_referencia: str) -> list[dict[str, Any]]:
        query = """
            SELECT
                ID_CARGA AS id_carga,
                LTRIM(RTRIM(NM_ORIGEM)) AS origem,
                NU_REMESSA AS remessa,
                CASE
                    WHEN TP_STATUS = 0 THEN 'NADA'
                    WHEN TP_STATUS = 1 THEN 'AGUARDANDO'
                    WHEN TP_STATUS = 2 THEN 'ERRO'
                    WHEN TP_STATUS = 3 THEN 'EM ANDAMENTO'
                    WHEN TP_STATUS = 4 THEN 'PROCESSADO'
                END AS status_carga,
                DT_INICIO AS dt_inicio,
                DT_FIM AS dt_fim,
                NM_ARQUIVO AS arquivo
            FROM [dbo].[TB_CARGA] WITH(NOLOCK)
            WHERE CAST(DT_INICIO AS DATE) = CONVERT(date, ?)
            ORDER BY DT_INICIO DESC, ID_CARGA DESC
        """
        rows = self._db.execute(
            query=query,
            parametros=(data_referencia,),
            fetch=True,
        )

        return [
            {
                "id_carga": int(row.get("id_carga") or 0),
                "origem": (row.get("origem") or "").strip(),
                "remessa": str(row.get("remessa") or "").strip(),
                "status": str(row.get("status_carga") or "").strip().upper(),
                "inicio": self._formatar_data(row.get("dt_inicio")),
                "fim": self._formatar_data(row.get("dt_fim")),
                "arquivo": str(row.get("arquivo") or "").strip(),
            }
            for row in (rows or [])
        ]

    def _formatar_data(self, valor: Any) -> str:
        if isinstance(valor, datetime):
            return valor.strftime("%d/%m/%Y %H:%M:%S")
        return str(valor or "").strip()
