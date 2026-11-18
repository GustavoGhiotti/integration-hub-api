import os
import sys
import threading
import subprocess

from waitress import serve
from app import create_app
from src.infrastructure.external.telegram.telegram_bot import TelegramBot


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "sim", "on"}


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

def start_bot_process() -> None:
    run_bot_path = os.path.join(os.path.dirname(__file__), "run_bot.py")
    subprocess.Popen([sys.executable, run_bot_path])

app = create_app()

if __name__ == "__main__":
    homologacao = env_bool("HOMOLOGACAO")
    permitir_bot = not homologacao or env_bool("ENABLE_TELEGRAM_BOT_HOMOLOGACAO")

    if permitir_bot:
        # Os dois modos sao mutuamente exclusivos para nunca abrir dois
        # pollings com o mesmo token dentro da mesma instancia da API.
        if env_bool("BOT_AUTOSTART"):
            start_bot_process()
        elif env_bool("ENABLE_TELEGRAM_BOT"):
            bot_thread = threading.Thread(target=run_bot, daemon=True)
            bot_thread.start()
    elif env_bool("BOT_AUTOSTART") or env_bool("ENABLE_TELEGRAM_BOT"):
        print("[STARTUP] Bot Telegram desabilitado no ambiente de homologacao")

    threads = 32
    connection_limit = 512
    channel_timeout = 90
    backlog = 128
    serve(
        app,
        host="0.0.0.0",
        port=8030,
        threads=threads,
        connection_limit=connection_limit,
        channel_timeout=channel_timeout,
        backlog=backlog,
    )
