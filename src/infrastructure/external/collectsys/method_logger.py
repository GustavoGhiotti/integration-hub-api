import json
import re
import time
from functools import wraps
from typing import Any

from src.infrastructure.logging.logger_config import get_log_context, setup_logger


_MAX_LOG_VALUE_LENGTH = 20_000
_PREVIEW_LOG_VALUE_LENGTH = 4_000
_XML_SENSITIVE_TAGS = ("senhaUsuario", "senha", "pwd", "token", "authorization")
_XML_DOCUMENT_TAGS = ("cpf", "cnpj", "regis")


def _to_snake_case(value: str) -> str:
    value = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", value)
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    return value.lower()


def _route_slug() -> str:
    path = get_log_context().get("path") or ""
    if not path or path == "-":
        return "sem_rota"

    slug = path.strip("/").replace("/", "_").replace("-", "_")
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", slug)
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug.lower() or "sem_rota"


def _mask_sensitive(text: str) -> str:
    masked = text

    def mask_document(match):
        final_documento = re.sub(r"\D", "", match.group(2))[-4:]
        return f"{match.group(1)}***{final_documento}{match.group(3)}"

    for tag in _XML_SENSITIVE_TAGS:
        patterns = (
            re.compile(rf"(<{tag}>)(.*?)(</{tag}>)", flags=re.IGNORECASE | re.DOTALL),
            re.compile(rf"(&lt;{tag}&gt;)(.*?)(&lt;/{tag}&gt;)", flags=re.IGNORECASE | re.DOTALL),
        )
        for pattern in patterns:
            masked = pattern.sub(r"\1***\3", masked)

    for tag in _XML_DOCUMENT_TAGS:
        patterns = (
            re.compile(rf"(<{tag}>)(.*?)(</{tag}>)", flags=re.IGNORECASE | re.DOTALL),
            re.compile(rf"(&lt;{tag}&gt;)(.*?)(&lt;/{tag}&gt;)", flags=re.IGNORECASE | re.DOTALL),
        )
        for pattern in patterns:
            masked = pattern.sub(mask_document, masked)

    masked = re.sub(
        r'("(?:senha|senhaUsuario|token|authorization)"\s*:\s*")[^"]*(")',
        r"\1***\2",
        masked,
        flags=re.IGNORECASE,
    )
    return masked


def serialize_log_value(value: Any, max_length: int = _MAX_LOG_VALUE_LENGTH) -> str:
    if value is None:
        return "null"

    try:
        if isinstance(value, str):
            text = value
        else:
            text = json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        text = repr(value)

    text = _mask_sensitive(text)
    if len(text) > max_length:
        return f"{text[:max_length]}...<truncated>"
    return text


def build_instance_context(instance: Any) -> dict[str, Any]:
    context = {}
    fields = (
        "servidor",
        "id_cedente",
        "id_cliente",
        "idCliente",
        "id_acordo",
        "plano",
        "valor_entrada",
        "parcela",
        "id_acao",
        "email",
    )

    for field in fields:
        if hasattr(instance, field):
            context[field] = getattr(instance, field)

    return context


def get_collectsys_method_logger(instance: Any, method_name: str):
    class_name = _to_snake_case(instance.__class__.__name__)
    route_slug = _route_slug()
    logger_name = f"collectsys.{route_slug}.{class_name}.{method_name}"
    file_name = f"rotas/{route_slug}/collectsys_{class_name}_{method_name}.log"
    return setup_logger(
        logger_name,
        file_name,
        daily_file=True,
        retention_days=7,
    )


def log_collectsys_method(method_name: str | None = None):
    def decorator(func):
        resolved_method_name = method_name or func.__name__

        @wraps(func)
        def wrapper(self, *args, **kwargs):
            logger = get_collectsys_method_logger(self, resolved_method_name)
            started_at = time.perf_counter()

            try:
                result = func(self, *args, **kwargs)
            except Exception as exc:
                duration_ms = int((time.perf_counter() - started_at) * 1000)
                logger.exception(
                    "method_exception %s",
                    json.dumps(
                        {
                            "class": self.__class__.__name__,
                            "method": resolved_method_name,
                            "context": build_instance_context(self),
                            "duration_ms": duration_ms,
                            "exception_type": type(exc).__name__,
                            "exception_message": serialize_log_value(str(exc)),
                        },
                        ensure_ascii=False,
                        default=str,
                    ),
                )
                raise
            return result

        return wrapper

    return decorator
