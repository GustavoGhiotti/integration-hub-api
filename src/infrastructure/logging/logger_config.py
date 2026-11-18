import os
import sys
import json
import uuid
import time
import logging
import threading
from contextvars import ContextVar
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler

# Diretorio base dos logs
LOG_DIR = os.path.join(os.path.dirname(__file__), "../../../logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Armazena contexto por request e propaga em asyncio/to_thread
_log_context: ContextVar[dict] = ContextVar("log_context", default={})
_logger_setup_lock = threading.Lock()

# CONTEXTO DE LOG (para armazenar dados da requisição)
def set_log_context(request_id=None, user=None, path=None, method=None, ip=None, reset=False, **extra):
    """Define o contexto do log para a thread atual"""
    context = {} if reset else dict(_log_context.get())
    if request_id is not None:
        context["request_id"] = request_id
    if user is not None:
        context["user"] = user
    if path is not None:
        context["path"] = path
    if method is not None:
        context["method"] = method
    if ip is not None:
        context["ip"] = ip
    for key, value in extra.items():
        if value is not None:
            context[key] = value
    _log_context.set(context)


def get_log_context() -> dict:
    """Retorna o contexto atual de log da thread."""
    return dict(_log_context.get())

# Formatador personalizado
class ContextFormatter(logging.Formatter):
    """Formata os logs incluindo contexto de requisição"""
    def format(self, record):
        context = get_log_context()
        record.request_id = context.get("request_id", "-")
        record.user = context.get("user", "-")
        record.path = context.get("path", "-")
        record.method = context.get("method", "-")
        record.ip = context.get("ip", "-")

        log_format = (
            "%(asctime)s [%(levelname)s] [REQ=%(request_id)s] [USER=%(user)s] "
            "%(name)s - %(method)s %(path)s (%(ip)s) - %(message)s"
        )
        formatter = logging.Formatter(log_format)
        return formatter.format(record)

class JsonFormatter(logging.Formatter):
    """Formata o log com JSON estruturado"""
    def format(self,record):
        context = get_log_context()
        log_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": context.get("request_id", "-"),
            "user": context.get("user", "-"),
            "method": context.get("method", "-"),
            "path": context.get("path", "-"),
            "ip": context.get("ip", "-"),
            "message": record.getMessage(),
        }
        return json.dumps(log_record, ensure_ascii=False)


class DailyFileHandler(logging.FileHandler):
    """Grava em <nome>_YYYY-MM-DD.log e remove arquivos antigos."""

    def __init__(self, base_filename: str, retention_days: int = 7, encoding: str = "utf-8"):
        self.base_filename = base_filename
        self.retention_days = retention_days
        self.current_date = self._today()
        dated_filename = self._build_dated_filename(self.current_date)
        os.makedirs(os.path.dirname(dated_filename), exist_ok=True)
        super().__init__(dated_filename, encoding=encoding)

    def _today(self) -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def _build_dated_filename(self, day: str) -> str:
        directory, filename = os.path.split(self.base_filename)
        name, ext = os.path.splitext(filename)
        ext = ext or ".log"
        return os.path.join(directory, f"{name}_{day}{ext}")

    def _cleanup_old_files(self):
        directory, filename = os.path.split(self.base_filename)
        name, ext = os.path.splitext(filename)
        ext = ext or ".log"
        prefix = f"{name}_"
        cutoff = datetime.now().date() - timedelta(days=self.retention_days - 1)

        for entry in os.listdir(directory):
            if not entry.startswith(prefix) or not entry.endswith(ext):
                continue

            date_part = entry[len(prefix):-len(ext)]
            try:
                file_date = datetime.strptime(date_part, "%Y-%m-%d").date()
            except ValueError:
                continue

            if file_date < cutoff:
                try:
                    os.remove(os.path.join(directory, entry))
                except OSError:
                    pass

    def _rotate_if_needed(self):
        today = self._today()
        if today == self.current_date:
            return

        self.acquire()
        try:
            if self.stream:
                self.stream.close()
                self.stream = None

            self.current_date = today
            self.baseFilename = os.path.abspath(self._build_dated_filename(today))
            self.stream = self._open()
            self._cleanup_old_files()
        finally:
            self.release()

    def emit(self, record):
        self._rotate_if_needed()
        super().emit(record)

def setup_global_logger(json_output=False):
    """
    Configura o logger principal da aplicação.
    """
    logger = logging.getLogger("app")

    if not logger.handlers:
        log_path = os.path.join(LOG_DIR, "app.log")
        handler = RotatingFileHandler(
            log_path, maxBytes=10_000_000, backupCount=5, encoding="utf-8"
        )

        formatter = JsonFormatter() if json_output else ContextFormatter()
        handler.setFormatter(formatter)

        logger.addHandler(handler)
        logger.addHandler(logging.StreamHandler(sys.stdout))
        logger.setLevel(logging.INFO)

    return logger


def setup_logger(
    name: str,
    filename: str,
    enabled: bool = True,
    *,
    daily_file: bool = False,
    retention_days: int = 7,
) -> logging.Logger:
    """
    Cria um logger dedicado e padronizado (por rota, módulo ou serviço).
    """
    logger = logging.getLogger(name)

    with _logger_setup_lock:
        if not logger.handlers and enabled:
            log_path = os.path.join(LOG_DIR, filename)
            if daily_file:
                handler = DailyFileHandler(
                    log_path,
                    retention_days=retention_days,
                    encoding="utf-8",
                )
            else:
                handler = RotatingFileHandler(
                    log_path, maxBytes=5_000_000, backupCount=5, encoding="utf-8"
                )
            formatter = ContextFormatter()
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            logger.propagate = False

        if not enabled:
            logger.disabled = True

    return logger
