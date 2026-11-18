import os

from src.infrastructure.external.telegram.telegram_bot import TelegramBot


def run_bot() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    usuario = os.getenv("EASYCOLLECTOR_USER")
    senha = os.getenv("EASYCOLLECTOR_PASSWORD")

    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN nao definido")
    if not usuario or not senha:
        raise RuntimeError("EASYCOLLECTOR_USER/EASYCOLLECTOR_PASSWORD nao definidos")

    TelegramBot(
        token=token,
        usuario=usuario,
        senha=senha
    ).run()


if __name__ == "__main__":
    run_bot()
