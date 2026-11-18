from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any


_SENSITIVE_PARTS = ("authorization", "password", "senha", "pwd", "token", "apikey", "api_key", "cookie", "secret")
_BINARY_PARTS = ("base64", "arquivo", "pdf", "imagem", "image", "qrcode", "anexo")
_DOCUMENT_PARTS = ("cpf", "cnpj", "documento", "regis")
_PHONE_PARTS = ("telefone", "celular", "phone", "whatsapp")
_BASE64_RE = re.compile(r"^[A-Za-z0-9+/=\r\n]{1024,}$")


@dataclass(frozen=True)
class SanitizedPayload:
    text: str | None
    original_size: int
    truncated: bool


def _normalizar(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9_]", "", text)


def _sha256_bytes(value: str) -> bytes:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).digest()


def _mask_document(value: Any) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) <= 4:
        return "*" * len(digits)
    return f"{'*' * (len(digits) - 4)}{digits[-4:]}"


def _binary_marker(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, bytes) else str(value or "").encode("utf-8", errors="replace")
    if isinstance(raw, str):
        raw = raw.encode("utf-8", errors="replace")
    return {"removido": "conteudo_binario", "tamanho_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def _sanitize(value: Any, key: str = "") -> Any:
    normalized_key = _normalizar(key)
    if any(part in normalized_key for part in _SENSITIVE_PARTS):
        return "***"
    if any(part in normalized_key for part in _BINARY_PARTS) and value not in (None, "", [], {}):
        return _binary_marker(value)
    if any(part in normalized_key for part in _DOCUMENT_PARTS):
        return _mask_document(value)
    if any(part in normalized_key for part in _PHONE_PARTS):
        digits = re.sub(r"\D", "", str(value or ""))
        return f"***{digits[-4:]}" if digits else None

    if isinstance(value, dict):
        return {str(k): _sanitize(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_sanitize(item) for item in value]
    if isinstance(value, bytes):
        return _binary_marker(value)
    if isinstance(value, str) and _BASE64_RE.fullmatch(value.strip()):
        return _binary_marker(value)
    return value


def _sanitize_xml(text: str) -> str:
    result = text
    for tag in (*_SENSITIVE_PARTS, *_BINARY_PARTS, *_DOCUMENT_PARTS, *_PHONE_PARTS):
        pattern = re.compile(rf"(<[^>]*{re.escape(tag)}[^>]*>)(.*?)(</[^>]+>)", re.IGNORECASE | re.DOTALL)

        def replace(match):
            value = match.group(2)
            sanitized = _sanitize(value, tag)
            replacement = sanitized if isinstance(sanitized, str) else json.dumps(sanitized, ensure_ascii=False)
            return f"{match.group(1)}{replacement}{match.group(3)}"

        result = pattern.sub(replace, result)

        escaped_pattern = re.compile(
            rf"(&lt;[^&]*{re.escape(tag)}[^&]*&gt;)(.*?)(&lt;/[^&]+&gt;)",
            re.IGNORECASE | re.DOTALL,
        )
        result = escaped_pattern.sub(replace, result)
    return result


def sanitize_payload(value: Any, max_bytes: int = 65536) -> SanitizedPayload:
    if value is None:
        return SanitizedPayload(None, 0, False)

    if isinstance(value, str):
        original = value.encode("utf-8", errors="replace")
        try:
            parsed = json.loads(value)
            text = json.dumps(_sanitize(parsed), ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            text = _sanitize_xml(value)
    else:
        try:
            original = json.dumps(value, ensure_ascii=False, default=str).encode("utf-8", errors="replace")
        except TypeError:
            original = str(value).encode("utf-8", errors="replace")
        text = json.dumps(_sanitize(value), ensure_ascii=False, default=str)

    encoded = text.encode("utf-8", errors="replace")
    truncated = len(encoded) > max_bytes
    if truncated:
        encoded = encoded[:max_bytes]
        text = encoded.decode("utf-8", errors="ignore") + "...[TRUNCADO]"
    return SanitizedPayload(text, len(original), truncated)


def extract_dimensions(*sources: Any) -> dict[str, Any]:
    found: dict[str, Any] = {}

    aliases = {
        "id_cliente": {"idcliente", "clienteid"},
        "id_cedente": {"idcedente", "cedenteid", "idcredor", "codcred"},
        "nome_cedente": {"nomecedente", "nmcedente", "nomecredor", "nmcredor"},
        "id_contrato": {"idcontrato", "contrato", "numerocontrato"},
        "id_acordo": {"idacordo", "acordo", "codigoacordo", "codigocalculo"},
    }
    documents: list[str] = []
    phones: list[str] = []

    def walk(value: Any):
        if isinstance(value, dict):
            for key, item in value.items():
                normalized = _normalizar(key)
                candidate = item[0] if isinstance(item, (list, tuple)) and len(item) == 1 else item
                if normalized in {"cedente", "credor"} and candidate not in (None, ""):
                    text = str(candidate).strip()
                    if re.fullmatch(r"\d+", text):
                        found.setdefault("id_cedente", int(text))
                    else:
                        found.setdefault("nome_cedente", candidate)
                for target, names in aliases.items():
                    if target not in found and normalized in names and item not in (None, ""):
                        found[target] = item
                if any(part in normalized for part in _DOCUMENT_PARTS) and item not in (None, ""):
                    documents.append(str(item))
                if any(part in normalized for part in _PHONE_PARTS) and item not in (None, ""):
                    phones.append(str(item))
                walk(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item)
        elif isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith(("{", "[")):
                try:
                    walk(json.loads(stripped))
                    return
                except ValueError:
                    pass
            for tag, content in re.findall(r"<([A-Za-z0-9_:.-]+)[^>]*>([^<>]*)</\1>", value, re.DOTALL):
                walk({tag.split(":")[-1]: content.strip()})

    for source in sources:
        walk(source)

    if documents:
        digits = re.sub(r"\D", "", documents[0])
        if digits:
            found["documento_hash"] = _sha256_bytes(digits)
            found["documento_mascarado"] = _mask_document(digits)
    if phones:
        digits = re.sub(r"\D", "", phones[0])
        found["telefone_final"] = digits[-4:] or None
    try:
        found["id_cedente"] = int(found["id_cedente"]) if found.get("id_cedente") is not None else None
    except (TypeError, ValueError):
        found["id_cedente"] = None
    return found
