from __future__ import annotations

from src.infrastructure.database.sql_server_connection import SQLServerConnection


class EasycollectorTarefaRepository:
    def __init__(self, server: str = "10.0.0.65") -> None:
        self._db = SQLServerConnection(server=server, database="easycollector")

    def buscar_por_termo(self, termo: str, limite: int = 20) -> list[str]:
        termo = (termo or "").strip()
        if not termo:
            return []

        limite = max(1, min(limite, 50))
        query = f"""
            SELECT TOP {limite}
                LTRIM(RTRIM(nm_tarefa)) AS nm_tarefa
            FROM [dbo].[TB_TAREFA] WITH(NOLOCK)
            WHERE nm_tarefa IS NOT NULL
              AND LTRIM(RTRIM(nm_tarefa)) <> ''
              AND nm_tarefa LIKE ?
            ORDER BY nm_tarefa
        """
        rows = self._db.execute(
            query=query,
            parametros=(f"%{termo}%",),
            fetch=True
        )

        vistos: set[str] = set()
        tarefas: list[str] = []
        for row in rows or []:
            nome = (row.get("nm_tarefa") or "").strip()
            if not nome:
                continue
            chave = nome.lower()
            if chave in vistos:
                continue
            vistos.add(chave)
            tarefas.append(nome)
        return tarefas
