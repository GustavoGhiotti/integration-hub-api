import asyncio
from typing import Any

from src.infrastructure.database.sql_server_connection import (
    SQLServerConnection,
)
from src.shared.utils.env_load import DB_66


class GoogleChatRepository:
    def __init__(self) -> None:
        self._db = SQLServerConnection(
            server=DB_66,
            database="DB_DESENVOLVIMENTO",
        )

    async def buscar_por_id(
        self,
        id_chat: int,
    ) -> dict[str, Any] | None:
        query = """
            SELECT TOP 1
                ID_CHAT,
                NM_CHAT,
                URL_CHAT_WEBHOOK,
                ATIVO
            FROM [APIAcme].[TB_GOOGLE_CHAT] 
            WHERE ID_CHAT = ?;
        """

        registros = await asyncio.to_thread(
            self._db.execute,
            query=query,
            parametros=(id_chat,),
            fetch=True,
        )

        return registros[0] if registros else None

    async def buscar_por_nome(
        self,
        nome_chat: str,
    ) -> dict[str, Any] | None:
        query = """
            SELECT TOP 1
                ID_CHAT,
                NM_CHAT,
                URL_CHAT_WEBHOOK,
                ATIVO
            FROM [APIAcme].[TB_GOOGLE_CHAT] 
            WHERE NM_CHAT = ?;
        """

        registros = await asyncio.to_thread(
            self._db.execute,
            query=query,
            parametros=(nome_chat,),
            fetch=True,
        )

        return registros[0] if registros else None