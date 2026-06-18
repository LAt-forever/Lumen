from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Iterable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from service import db as dbmod
from service.models import IngestionJob

TERMINAL_JOB_STATUSES = ("succeeded", "failed", "canceled")


@dataclass(frozen=True)
class BackupResult:
    backup_path: Path
    database_path: Path
    created_at: str


@dataclass(frozen=True)
class CleanupResult:
    deleted_count: int
    cutoff: datetime
    statuses: tuple[str, ...]


def backup_sqlite(database_path: Path, output_path: Path) -> BackupResult:
    database_path = database_path.expanduser().resolve()
    output_path = output_path.expanduser().resolve()
    if not database_path.exists():
        raise FileNotFoundError(f"SQLite database not found: {database_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now(UTC).isoformat()
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(database_path, "database.sqlite")
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(database_path) + suffix)
            if sidecar.exists():
                archive.write(sidecar, f"database.sqlite{suffix}")
        archive.writestr(
            "metadata.json",
            json.dumps(
                {
                    "created_at": created_at,
                    "database_path": str(database_path),
                    "format": "lumen-sqlite-backup-v1",
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    return BackupResult(output_path, database_path, created_at)


def restore_sqlite(backup_path: Path, destination_path: Path, overwrite: bool = False) -> Path:
    backup_path = backup_path.expanduser().resolve()
    destination_path = destination_path.expanduser().resolve()
    if destination_path.exists() and not overwrite:
        raise FileExistsError(f"Destination already exists: {destination_path}")
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(backup_path) as archive:
        names = set(archive.namelist())
        if "database.sqlite" not in names:
            raise ValueError("Backup archive does not contain database.sqlite")
        with archive.open("database.sqlite") as source, destination_path.open("wb") as destination:
            shutil.copyfileobj(source, destination)
        for suffix in ("-wal", "-shm"):
            member = f"database.sqlite{suffix}"
            sidecar = Path(str(destination_path) + suffix)
            if member in names:
                with archive.open(member) as source, sidecar.open("wb") as destination:
                    shutil.copyfileobj(source, destination)
            elif sidecar.exists():
                sidecar.unlink()
    return destination_path


def export_sqlite_ndjson(database_path: Path, output_dir: Path) -> dict[str, int]:
    database_path = database_path.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    if not database_path.exists():
        raise FileNotFoundError(f"SQLite database not found: {database_path}")
    output_dir.mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = {}
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        table_names = _sqlite_table_names(connection)
        for table_name in table_names:
            rows = connection.execute(f'SELECT * FROM "{table_name}"').fetchall()
            counts[table_name] = len(rows)
            with (output_dir / f"{table_name}.ndjson").open("w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(dict(row), ensure_ascii=False, default=str))
                    handle.write("\n")
        (output_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "created_at": datetime.now(UTC).isoformat(),
                    "source_database": str(database_path),
                    "format": "lumen-sqlite-ndjson-v1",
                    "tables": counts,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    finally:
        connection.close()
    return counts


def cleanup_ingestion_jobs(
    db: Session,
    older_than_days: int = 30,
    statuses: Iterable[str] = TERMINAL_JOB_STATUSES,
) -> CleanupResult:
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=older_than_days)
    status_tuple = tuple(statuses)
    job_ids = list(
        db.scalars(
            select(IngestionJob.id).where(
                IngestionJob.status.in_(status_tuple),
                IngestionJob.finished_at.is_not(None),
                IngestionJob.finished_at < cutoff,
            )
        )
    )
    if job_ids:
        db.execute(delete(IngestionJob).where(IngestionJob.id.in_(job_ids)))
        db.commit()
    return CleanupResult(deleted_count=len(job_ids), cutoff=cutoff, statuses=status_tuple)


def _sqlite_table_names(connection: sqlite3.Connection) -> list[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [row["name"] for row in rows]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lumen maintenance commands")
    subcommands = parser.add_subparsers(dest="command", required=True)

    backup = subcommands.add_parser("backup-sqlite", help="Create a zipped SQLite backup")
    backup.add_argument("--database", required=True)
    backup.add_argument("--output", required=True)

    restore = subcommands.add_parser("restore-sqlite", help="Restore a zipped SQLite backup")
    restore.add_argument("--backup", required=True)
    restore.add_argument("--destination", required=True)
    restore.add_argument("--overwrite", action="store_true")

    export = subcommands.add_parser("export-sqlite", help="Export SQLite tables as NDJSON for Postgres migration")
    export.add_argument("--database", required=True)
    export.add_argument("--output-dir", required=True)

    cleanup = subcommands.add_parser("cleanup-ingestion-jobs", help="Delete old terminal ingestion job history")
    cleanup.add_argument("--older-than-days", type=int, default=30)
    cleanup.add_argument("--statuses", default=",".join(TERMINAL_JOB_STATUSES))

    args = parser.parse_args(argv)
    if args.command == "backup-sqlite":
        result = backup_sqlite(Path(args.database), Path(args.output))
        print(json.dumps(result.__dict__, default=str, ensure_ascii=False))
        return 0
    if args.command == "restore-sqlite":
        restored = restore_sqlite(Path(args.backup), Path(args.destination), overwrite=args.overwrite)
        print(json.dumps({"restored": str(restored)}, ensure_ascii=False))
        return 0
    if args.command == "export-sqlite":
        counts = export_sqlite_ndjson(Path(args.database), Path(args.output_dir))
        print(json.dumps({"tables": counts}, ensure_ascii=False))
        return 0
    if args.command == "cleanup-ingestion-jobs":
        dbmod.init_db()
        with dbmod.SessionLocal() as db:
            result = cleanup_ingestion_jobs(
                db,
                older_than_days=args.older_than_days,
                statuses=[status.strip() for status in args.statuses.split(",") if status.strip()],
            )
        print(json.dumps(result.__dict__, default=str, ensure_ascii=False))
        return 0
    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
