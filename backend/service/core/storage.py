from pathlib import Path
from uuid import uuid4

from service.config import Settings

settings = Settings()
UPLOAD_ROOT = Path(settings.upload_storage_path)


def ensure_upload_root() -> None:
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)


_MAX_FILENAME_LEN = 200


def _safe_filename(name: str) -> str:
    """Truncate overly long filenames to prevent filesystem limits."""
    if len(name) <= _MAX_FILENAME_LEN:
        return name
    ext = Path(name).suffix
    stem = Path(name).stem
    max_stem = _MAX_FILENAME_LEN - len(ext)
    return f"{stem[:max_stem]}{ext}"


def save_temp_upload(file_data: bytes, original_filename: str) -> str:
    ensure_upload_root()
    safe_name = _safe_filename(original_filename)
    ext = Path(safe_name).suffix
    temp_dir = UPLOAD_ROOT / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / f"{uuid4().hex}{ext}"
    temp_path.write_bytes(file_data)
    return str(temp_path.relative_to(UPLOAD_ROOT))


def move_to_final(temp_relative_path: str, source_id: int, original_filename: str) -> str:
    temp_path = resolve_file_path(temp_relative_path)
    if not temp_path.exists():
        raise FileNotFoundError(f"temp file not found: {temp_relative_path}")

    final_dir = UPLOAD_ROOT / str(source_id)
    final_dir.mkdir(parents=True, exist_ok=True)
    final_path = final_dir / original_filename

    # Handle duplicate filenames by appending a counter
    counter = 1
    stem = final_path.stem
    suffix = final_path.suffix
    while final_path.exists():
        final_path = final_dir / f"{stem}_{counter}{suffix}"
        counter += 1

    temp_path.rename(final_path)
    return str(final_path.relative_to(UPLOAD_ROOT))


def resolve_file_path(relative_path: str) -> Path:
    # Reject null bytes early to avoid low-level path errors and potential injection
    if "\x00" in relative_path:
        raise ValueError(f"path traversal detected: {relative_path}")
    resolved = (UPLOAD_ROOT / relative_path).resolve()
    # Path traversal protection: ensure resolved path is inside UPLOAD_ROOT
    try:
        resolved.relative_to(UPLOAD_ROOT.resolve())
    except ValueError:
        raise ValueError(f"path traversal detected: {relative_path}")
    return resolved
