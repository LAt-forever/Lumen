import logging

from service.config import Settings
from service.core.security import (
    SecretRedactionFilter,
    decrypt_secret,
    encrypt_secret,
    redact_text,
)


def test_encrypt_secret_round_trips_with_local_key(tmp_path):
    settings = Settings(data_dir=tmp_path)

    encrypted = encrypt_secret("secret-value", settings)

    assert encrypted is not None
    assert encrypted.startswith("lumen:v1:")
    assert "secret-value" not in encrypted
    assert decrypt_secret(encrypted, settings) == "secret-value"


def test_decrypt_secret_allows_legacy_plaintext():
    assert decrypt_secret("legacy-secret") == "legacy-secret"


def test_redact_text_masks_common_secret_shapes():
    message = "Bearer abcdefghijklmnop and sk-abcdefghijklmnop and custom-secret"

    redacted = redact_text(message, ["custom-secret"])

    assert "abcdefghijklmnop" not in redacted
    assert "custom-secret" not in redacted
    assert "[redacted-secret]" in redacted


def test_secret_redaction_filter_masks_log_record_args():
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="failed with %s",
        args=("sk-abcdefghijklmnop",),
        exc_info=None,
    )

    assert SecretRedactionFilter().filter(record) is True
    assert record.args == ("[redacted-secret]",)


def test_secret_redaction_filter_preserves_non_string_args():
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="processed %d records",
        args=(3,),
        exc_info=None,
    )

    assert SecretRedactionFilter().filter(record) is True
    assert record.args == (3,)
