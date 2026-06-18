from __future__ import annotations

import base64
import hashlib
import logging
import re
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from service.config import Settings, get_settings

SECRET_PREFIX = "lumen:v1:"
_API_KEY_RE = re.compile(r"\b(?:sk|rk|pk|key)-[A-Za-z0-9_\-]{12,}\b")
_BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9_\-.=]{12,}", re.IGNORECASE)
_LUMEN_TOKEN_RE = re.compile(r"lumen:v1:[A-Za-z0-9_\-=]+")
_LOG_RECORD_FACTORY_CONFIGURED = False


def encrypt_secret(value: str | None, settings: Settings | None = None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if stripped.startswith(SECRET_PREFIX):
        return stripped
    token = _fernet(settings).encrypt(stripped.encode("utf-8")).decode("ascii")
    return f"{SECRET_PREFIX}{token}"


def decrypt_secret(value: str | None, settings: Settings | None = None) -> str | None:
    if value is None:
        return None
    if not value.startswith(SECRET_PREFIX):
        return value
    token = value[len(SECRET_PREFIX) :].encode("ascii")
    try:
        return _fernet(settings).decrypt(token).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Stored secret could not be decrypted with the configured local key") from exc


def redact_text(message: str, secrets: list[str | None] | None = None) -> str:
    redacted = _LUMEN_TOKEN_RE.sub("[redacted-secret]", message)
    redacted = _BEARER_RE.sub("Bearer [redacted-secret]", redacted)
    redacted = _API_KEY_RE.sub("[redacted-secret]", redacted)
    for secret in secrets or []:
        if secret:
            redacted = redacted.replace(secret, "[redacted-secret]")
    return redacted


class SecretRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_text(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {key: _redact_log_arg(value) for key, value in record.args.items()}
            else:
                record.args = tuple(_redact_log_arg(value) for value in record.args)
        return True


def configure_log_redaction() -> None:
    global _LOG_RECORD_FACTORY_CONFIGURED
    if _LOG_RECORD_FACTORY_CONFIGURED:
        return
    current_factory = logging.getLogRecordFactory()
    redaction_filter = SecretRedactionFilter()

    def redacting_factory(*args, **kwargs):
        record = current_factory(*args, **kwargs)
        redaction_filter.filter(record)
        return record

    logging.setLogRecordFactory(redacting_factory)
    _LOG_RECORD_FACTORY_CONFIGURED = True


def _redact_log_arg(value):
    if isinstance(value, str):
        return redact_text(value)
    return value


def _fernet(settings: Settings | None = None) -> Fernet:
    key = _load_or_create_key(settings or get_settings())
    return Fernet(key)


def _load_or_create_key(settings: Settings) -> bytes:
    if settings.api_key_encryption_key:
        return _normalize_key(settings.api_key_encryption_key)

    path = _secret_key_path(settings)
    if path.exists():
        return _normalize_key(path.read_text(encoding="utf-8").strip())

    path.parent.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    path.write_text(key.decode("ascii"), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return key


def _secret_key_path(settings: Settings) -> Path:
    if settings.secret_key_path is not None:
        return settings.secret_key_path
    return settings.data_dir / "lumen-local-secret.key"


def _normalize_key(raw_key: str) -> bytes:
    candidate = raw_key.strip().encode("utf-8")
    try:
        Fernet(candidate)
    except Exception:
        digest = hashlib.sha256(candidate).digest()
        return base64.urlsafe_b64encode(digest)
    return candidate
