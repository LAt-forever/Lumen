from pathlib import Path
from tempfile import NamedTemporaryFile

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from service.core.knowledge import KnowledgeService
from service.core.parsing import parse_html, parse_pdf
from service.db import get_db
from service.repositories.chunks import ChunkRepository
from service.repositories.sources import SourceRepository
from service.schemas import LinkCapture, SourceCreate, SourceDetailRead, SourceRead

router = APIRouter(prefix="/api/sources", tags=["sources"])


_TEXT_SUFFIXES = {".txt": "text", ".md": "markdown"}


def _fetch_url_html(url: str) -> str:
    response = httpx.get(url, follow_redirects=True, timeout=12)
    response.raise_for_status()
    return response.text


def _source_type_for_filename(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in _TEXT_SUFFIXES:
        return _TEXT_SUFFIXES[suffix]
    if suffix == ".pdf":
        return "pdf"
    return "text"


def _failed_source(sources: SourceRepository, data: SourceCreate, message: str):
    source = sources.create(data)
    sources.mark_failed(source.id, message)
    refreshed = sources.get(source.id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return refreshed


@router.post("", response_model=SourceRead)
def create_source(data: SourceCreate, db: Session = Depends(get_db)):
    return SourceRepository(db).create(data)


@router.post("/upload", response_model=SourceRead)
async def upload_source(file: UploadFile = File(...), db: Session = Depends(get_db)):
    sources = SourceRepository(db)
    filename = file.filename or "Untitled file"
    suffix = Path(filename).suffix.lower()
    source_type = _source_type_for_filename(filename)
    data = await file.read()

    try:
        if suffix in _TEXT_SUFFIXES:
            content = data.decode("utf-8").strip()
        elif suffix == ".pdf":
            with NamedTemporaryFile(suffix=".pdf") as tmp:
                tmp.write(data)
                tmp.flush()
                content = parse_pdf(tmp.name).strip()
        else:
            return _failed_source(
                sources,
                SourceCreate(title=filename, source_type=source_type, filename=filename),
                "Unsupported file type",
            )
    except Exception as exc:
        return _failed_source(
            sources,
            SourceCreate(title=filename, source_type=source_type, filename=filename),
            f"Could not parse file: {exc}",
        )

    if not content:
        return _failed_source(
            sources,
            SourceCreate(title=filename, source_type=source_type, filename=filename),
            "No text content found",
        )
    return sources.create(SourceCreate(title=filename, source_type=source_type, filename=filename, content=content))


@router.post("/link", response_model=SourceRead)
def capture_link(data: LinkCapture, db: Session = Depends(get_db)):
    sources = SourceRepository(db)
    try:
        html = _fetch_url_html(data.url)
        content = parse_html(html).strip()
        if not content:
            raise ValueError("No text content found")
    except Exception as exc:
        return _failed_source(
            sources,
            SourceCreate(title=data.url, source_type="link", url=data.url),
            str(exc),
        )
    return sources.create(SourceCreate(title=data.url, source_type="link", url=data.url, content=content))


@router.get("", response_model=list[SourceRead])
def list_sources(db: Session = Depends(get_db)):
    return SourceRepository(db).list()


@router.get("/{source_id}", response_model=SourceDetailRead)
def get_source(source_id: int, db: Session = Depends(get_db)):
    sources = SourceRepository(db)
    source = sources.get(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return SourceDetailRead.model_validate(
        {
            "id": source.id,
            "title": source.title,
            "source_type": source.source_type,
            "status": source.status,
            "url": source.url,
            "filename": source.filename,
            "error_message": source.error_message,
            "created_at": source.created_at,
            "chunk_count": ChunkRepository(db).count_for_source(source.id),
        }
    )


@router.post("/{source_id}/index", response_model=SourceRead)
def index_source(source_id: int, db: Session = Depends(get_db)):
    sources = SourceRepository(db)
    if sources.get(source_id) is None:
        raise HTTPException(status_code=404, detail="Source not found")
    knowledge = KnowledgeService(sources, ChunkRepository(db))
    knowledge.index_source(source_id)
    source = sources.get(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@router.delete("/{source_id}", status_code=204)
def delete_source(source_id: int, db: Session = Depends(get_db)):
    sources = SourceRepository(db)
    if sources.get(source_id) is None:
        raise HTTPException(status_code=404, detail="Source not found")
    ChunkRepository(db).delete_for_source(source_id)
    sources.delete(source_id)
    return Response(status_code=204)
