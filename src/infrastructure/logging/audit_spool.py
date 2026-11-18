from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


def _json_default(value: Any):
    if isinstance(value, datetime):
        return {"__audit_type__": "datetime", "value": value.isoformat()}
    if isinstance(value, bytes):
        return {"__audit_type__": "bytes", "value": value.hex()}
    raise TypeError(f"Tipo nao serializavel no spool: {type(value).__name__}")


def _json_object_hook(value: dict):
    audit_type = value.get("__audit_type__")
    if audit_type == "datetime":
        return datetime.fromisoformat(value["value"])
    if audit_type == "bytes":
        return bytes.fromhex(value["value"])
    return value


class AuditSpool:
    """Spool append-only: o request escreve localmente e nunca acessa o banco."""

    def __init__(self, directory: str | None = None, fsync: bool = False):
        default_dir = Path(__file__).resolve().parents[3] / "logs" / "auditoria_spool"
        self.directory = Path(directory or os.getenv("API_AUDIT_SPOOL_DIR") or default_dir)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.fsync = fsync
        self._lock = threading.Lock()
        self._instance_id = f"{os.getpid()}_{uuid.uuid4().hex}"
        self.active_path = self.directory / f"api_audit_{self._instance_id}.active.log"
        self._order_cache: dict[Path, tuple[int, int, str]] = {}

    def append(
        self,
        operation: str,
        execution_id: str,
        data: dict,
        homologacao: bool = False,
    ) -> bool:
        envelope = {
            "version": 1,
            "operation": operation,
            "execution_id": execution_id,
            "homologacao": bool(homologacao),
            "recorded_at": datetime.now().astimezone(),
            "data": data,
        }
        line = json.dumps(envelope, ensure_ascii=False, separators=(",", ":"), default=_json_default)
        with self._lock:
            with self.active_path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(line)
                stream.write("\n")
                stream.flush()
                if self.fsync:
                    os.fsync(stream.fileno())
        return True

    def rotate(self) -> Path | None:
        with self._lock:
            if not self.active_path.exists() or self.active_path.stat().st_size == 0:
                return None
            ready = self.directory / f"api_audit_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{uuid.uuid4().hex}.ready.log"
            os.replace(self.active_path, ready)
            return ready

    def ready_files(self) -> list[Path]:
        paths = list(self.directory.glob("api_audit_*.ready.log"))
        current = set(paths)
        self._order_cache = {path: key for path, key in self._order_cache.items() if path in current}
        return sorted(paths, key=self._order_key)

    def _order_key(self, path: Path) -> tuple[int, int, str]:
        """Ordena pelo evento, pois o nome pode ter sido alterado por retries antigos."""
        cached = self._order_cache.get(path)
        if cached is not None:
            return cached
        try:
            with path.open("r", encoding="utf-8") as stream:
                for line in stream:
                    if not line.strip():
                        continue
                    event = json.loads(line)
                    recorded = event.get("recorded_at", {})
                    value = recorded.get("value") if isinstance(recorded, dict) else recorded
                    timestamp = datetime.fromisoformat(value).timestamp() if value else path.stat().st_mtime
                    key = (0, int(timestamp * 1_000_000), path.name)
                    break
                else:
                    key = (1, int(path.stat().st_mtime * 1_000_000), path.name)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            key = (1, int(path.stat().st_mtime * 1_000_000), path.name)
        self._order_cache[path] = key
        return key

    def claim(self, ready_path: Path) -> Path | None:
        processing = ready_path.with_name(f"{ready_path.stem}.processing.{self._instance_id}.log")
        try:
            os.replace(ready_path, processing)
            return processing
        except (FileNotFoundError, PermissionError):
            return None

    def read(self, processing_path: Path) -> list[dict]:
        events = []
        with processing_path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    events.append(json.loads(line, object_hook=_json_object_hook))
                except (ValueError, TypeError) as exc:
                    raise ValueError(f"Evento invalido em {processing_path.name}, linha {line_number}") from exc
        return events

    def complete(self, processing_path: Path):
        processing_path.unlink(missing_ok=True)

    def release(self, processing_path: Path) -> Path:
        marker = ".ready.processing."
        if marker in processing_path.name:
            original_prefix = processing_path.name.split(marker, 1)[0]
            ready = self.directory / f"{original_prefix}.ready.log"
        else:
            ready = self.directory / f"api_audit_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{uuid.uuid4().hex}.ready.log"
        os.replace(processing_path, ready)
        return ready

    def quarantine(self, processing_path: Path) -> Path:
        invalid = self.directory / f"api_audit_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{uuid.uuid4().hex}.invalid.log"
        os.replace(processing_path, invalid)
        return invalid

    def recover_stale(self, minimum_age_seconds: int = 300):
        now = datetime.now().timestamp()
        stale_paths = list(self.directory.glob("api_audit_*.processing.*.log"))
        stale_paths.extend(path for path in self.directory.glob("api_audit_*.active.log") if path != self.active_path)
        for path in stale_paths:
            try:
                if path.stat().st_size and now - path.stat().st_mtime >= minimum_age_seconds:
                    self.release(path)
            except (FileNotFoundError, PermissionError, OSError):
                continue
