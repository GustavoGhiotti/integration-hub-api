import re

from src.infrastructure.external.gmail.gmail_chat_sender import (
    GmailChatSender,
)
from src.infrastructure.repositories.sql_google_chat_repository import (
    GoogleChatRepository,
)


TAMANHO_MAXIMO_MENSAGEM = 4000

PADRAO_NOME_CHAT = re.compile(
    r"^[A-Za-zÀ-ÖØ-öø-ÿ0-9 ]+$"
)


class GoogleChatService:
    def __init__(
        self,
        google_chat_repository: GoogleChatRepository,
        gmail_chat_sender: GmailChatSender,
    ) -> None:
        self._google_chat_repository = google_chat_repository
        self._gmail_chat_sender = gmail_chat_sender

    async def enviar_mensagem(
        self,
        mensagem: str,
        id_chat: int | None = None,
        nome_chat: str | None = None,
    ) -> bool:
        mensagem_normalizada = self._validar_mensagem(mensagem)
        chat = await self._buscar_chat(
            id_chat=id_chat,
            nome_chat=nome_chat,
        )

        webhook_url = self._obter_webhook_chat(chat)

        try:
            return await self._gmail_chat_sender.enviar_mensagem(
                webhook_url=webhook_url,
                mensagem=mensagem_normalizada,
            )
        except Exception as erro:
            raise RuntimeError(
                "Não foi possível enviar a mensagem para o Google Chat."
            ) from erro

    async def _buscar_chat(
        self,
        *,
        id_chat: int | None,
        nome_chat: str | None,
    ) -> dict[str, object]:
        self._validar_identificacao(
            id_chat=id_chat,
            nome_chat=nome_chat,
        )

        if id_chat is not None:
            chat = await self._google_chat_repository.buscar_por_id(
                id_chat
            )

            if chat is None:
                raise LookupError(
                    f"Chat com ID {id_chat} não encontrado."
                )

            return chat

        nome_normalizado = self._normalizar_nome_chat(nome_chat)

        chat = await self._google_chat_repository.buscar_por_nome(
            nome_normalizado
        )

        if chat is None:
            raise LookupError(
                f"Chat '{nome_normalizado}' não encontrado."
            )

        return chat

    @staticmethod
    def _obter_webhook_chat(
        chat: dict[str, object],
    ) -> str:
        ativo = bool(chat.get("ATIVO"))

        if not ativo:
            raise RuntimeError(
                "O chat informado está inativo."
            )

        webhook = str(
            chat.get("URL_CHAT_WEBHOOK") or ""
        ).strip()

        if not webhook:
            raise RuntimeError(
                "O chat informado não possui um webhook configurado."
            )

        return webhook
    
    @staticmethod
    def _validar_identificacao(
        *,
        id_chat: int | None,
        nome_chat: str | None,
    ) -> None:
        if id_chat is None and nome_chat is None:
            raise ValueError(
                "Informe o ID ou o nome do chat."
            )

        if id_chat is not None and nome_chat is not None:
            raise ValueError(
                "Informe apenas o ID ou o nome do chat, não ambos."
            )

        if id_chat is not None:
            if (
                not isinstance(id_chat, int)
                or isinstance(id_chat, bool)
                or id_chat <= 0
            ):
                raise ValueError(
                    "O ID do chat deve ser um número inteiro positivo."
                )

    @staticmethod
    def _normalizar_nome_chat(
        nome_chat: str | None,
    ) -> str:
        if not isinstance(nome_chat, str):
            raise ValueError(
                "O nome do chat é obrigatório."
            )

        nome_normalizado = nome_chat.strip()

        if not nome_normalizado:
            raise ValueError(
                "O nome do chat é obrigatório."
            )

        if not PADRAO_NOME_CHAT.fullmatch(nome_normalizado):
            raise ValueError(
                "O nome do chat deve conter apenas letras, números e espaços."
            )

        return nome_normalizado

    @staticmethod
    def _validar_mensagem(
        mensagem: str,
    ) -> str:
        if not isinstance(mensagem, str):
            raise ValueError(
                "A mensagem deve ser uma string."
            )

        mensagem_normalizada = mensagem.strip()

        if not mensagem_normalizada:
            raise ValueError(
                "A mensagem é obrigatória."
            )

        if len(mensagem_normalizada) > TAMANHO_MAXIMO_MENSAGEM:
            raise ValueError(
                "A mensagem excede o tamanho máximo permitido."
            )

        return mensagem_normalizada