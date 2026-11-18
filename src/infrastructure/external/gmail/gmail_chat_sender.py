import asyncio
import os
from urllib.parse import urlsplit

import httpx


class GmailChatSender:
    """Envia mensagens para espaços do Google Chat por webhook."""

    async def enviar_mensagem(
        self,
        webhook_url: str,
        mensagem: str,
    ) -> bool:
        url_normalizada = self._validar_webhook_url(webhook_url)
        mensagem_normalizada = self._validar_mensagem(mensagem)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    url_normalizada,
                    json={"text": mensagem_normalizada},
                )
                response.raise_for_status()

        except httpx.TimeoutException as erro:
            raise RuntimeError(
                "O envio da mensagem para o Google Chat excedeu o tempo limite."
            ) from erro

        except httpx.HTTPStatusError as erro:
            raise RuntimeError(
                "O Google Chat recusou o envio da mensagem."
            ) from erro

        except httpx.RequestError as erro:
            raise RuntimeError(
                "Não foi possível conectar ao Google Chat."
            ) from erro

        return True

    @staticmethod
    def _validar_webhook_url(
        webhook_url: str,
    ) -> str:
        url_normalizada = webhook_url.strip()

        if not url_normalizada:
            raise ValueError(
                "A URL do webhook do Google Chat é obrigatória."
            )

        url_parseada = urlsplit(url_normalizada)

        if (
            url_parseada.scheme != "https"
            or not url_parseada.netloc
        ):
            raise ValueError(
                "A URL do webhook deve iniciar com https://."
            )

        return url_normalizada

    @staticmethod
    def _validar_mensagem(
        mensagem: str,
    ) -> str:
        mensagem_normalizada = mensagem.strip()

        if not mensagem_normalizada:
            raise ValueError(
                "A mensagem do Google Chat não pode estar vazia."
            )

        return mensagem_normalizada
