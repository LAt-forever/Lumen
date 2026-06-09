# Phase 1.7: Ingestion Expansion — Design Specification

**Date:** 2026-06-09
**Status:** Approved
**Scope:** OCR, image knowledge base, enhanced web scraping, batch ingestion, additional file formats, bookmark import

---

## 1. Overview

Phase 1.7 expands Lumen's ingestion capabilities from 3 source types (note, text/pdf file, simple link) to 10 source types, adding OCR, image understanding, advanced web crawling, batch operations, and document format support.

### Current State (Phase 1.6)

| Source Type | Parser | Status |
|---|---|---|
| note / markdown / text | Plain text extraction | ✅ |
| pdf | `pypdf` text extraction (selectable-text only) | ✅ |
| link | `httpx` + `BeautifulSoup` simple fetch | ✅ |

### Target State (Phase 1.7)

| Source Type | Parser | New in 1.7 |
|---|---|---|
| note / markdown / text | `NoteParser` | Refactored |
| pdf | `PdfParser` (pypdf + Tesseract OCR fallback) | ✅ OCR |
| link | `WebParser` simple mode | Refactored |
| image | `ImageParser` (Tesseract OCR + Vision description) | ✅ |
| docx | `DocxParser` (python-docx) | ✅ |
| epub | `EpubParser` (ebooklib) | ✅ |
| bookmark | `BookmarkParser` (Netscape HTML) | ✅ |
| web_crawl | `WebParser` crawl mode (Playwright) | ✅ |

---

## 2. Architecture: Modular Parser Registry

### 2.1 Directory Structure

```
backend/service/core/parsers/
    __init__.py          # Registry: _registry dict + get_parser() + auto-import
    base.py              # ParseResult dataclass, ContentParser Protocol
    note_parser.py       # note, markdown, text
    pdf_parser.py        # pdf: pypdf text + PyMuPDF render + Tesseract OCR fallback
    image_parser.py      # image: Tesseract OCR + Vision API description
    docx_parser.py       # docx: python-docx
    epub_parser.py       # epub: ebooklib + BeautifulSoup
    web_parser.py        # link (httpx) + web_crawl (Playwright async)
    bookmark_parser.py   # bookmark: Netscape HTML parsing
```

### 2.2 Core Protocol

```python
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ParseResult:
    """Unified parser output"""
    text: str                      # Primary text for chunking/indexing
    title: str | None = None       # Optional title override
    metadata: dict[str, Any] = field(default_factory=dict)


class ContentParser(Protocol):
    """Content parser protocol. All parsers implement async parse()."""
    supported_types: frozenset[str]

    async def parse(self, source: Source, **kwargs) -> ParseResult:
        """Parse a Source into structured text.

        Args:
            source: The Source model (contains content, url, filename, source_type)
            **kwargs: Extra parameters (e.g., max_depth, max_pages for web crawl)
        """
        ...
```

### 2.3 Registry

```python
# __init__.py
_registry: dict[str, ContentParser] = {}


def register_parser(parser: ContentParser) -> None:
    for source_type in parser.supported_types:
        _registry[source_type] = parser


def get_parser(source_type: str) -> ContentParser:
    parser = _registry.get(source_type)
    if parser is None:
        raise ValueError(f"No parser registered for source type: {source_type}")
    return parser


# Auto-import and register all parsers on module load
def _init_registry():
    from .note_parser import NoteParser
    from .pdf_parser import PdfParser
    from .image_parser import ImageParser
    from .docx_parser import DocxParser
    from .epub_parser import EpubParser
    from .web_parser import WebParser
    from .bookmark_parser import BookmarkParser

    register_parser(NoteParser())
    register_parser(PdfParser())
    register_parser(ImageParser())
    register_parser(DocxParser())
    register_parser(EpubParser())
    register_parser(WebParser())
    register_parser(BookmarkParser())


_init_registry()
```

### 2.4 Migration of Existing parsing.py

The existing `backend/service/core/parsing.py` functions are migrated into parser classes:

- `parse_note()` → `NoteParser.parse()`
- `parse_html()` → `WebParser._parse_link()`
- `parse_pdf()` → `PdfParser._extract_text()` (pypdf path)

After migration, `parsing.py` is deleted. All imports updated to use `get_parser()`.

---

## 3. Data Model & Schema Changes

### 3.1 SourceType Extension

```python
SourceType = Literal[
    "note", "markdown", "text", "pdf", "link",
    "image",           # png, jpg, jpeg, gif, webp
    "docx",            # Word document
    "epub",            # E-book
    "bookmark",        # Single imported bookmark
    "web_crawl",       # Recursive web crawl result
]
```

### 3.2 Source Model — No Schema Migration Required

The existing `Source` model fields are sufficient:
- `filename` — stores relative path to uploaded file
- `content` — stores parsed text
- `url` — stores URL for link/bookmark/web_crawl
- `status` — pending/parsing/indexed/failed already exists

**New Repository Methods:**

```python
def update_title(self, source_id: int, title: str) -> Source: ...
def update_filename(self, source_id: int, filename: str) -> Source: ...
```

### 3.3 New Schemas

```python
class BulkUploadResult(BaseModel):
    """Batch upload result"""
    total: int
    succeeded: int
    failed: int
    sources: list[SourceRead]


class WebCrawlRequest(BaseModel):
    """Recursive web crawl request"""
    url: str = Field(min_length=1, max_length=1000)
    max_depth: int = Field(default=1, ge=1, le=3)       # 1-3 levels
    max_pages: int = Field(default=10, ge=1, le=50)     # Max 50 pages
    same_domain_only: bool = True


class BookmarkImportRequest(BaseModel):
    """Bookmark import request (Netscape HTML format)"""
    html_content: str = Field(min_length=1)
```

### 3.4 File Storage Strategy

New configuration: `upload_storage_path: str = "data/uploads"`

Upload flow:
1. Save uploaded file to `uploads/temp/{uuid}.{ext}`
2. Create `Source` with `filename="temp/{uuid}.{ext}"`
3. Parse content
4. On success: move to `uploads/{source_id}/{original_filename}`, update `Source.filename`
5. On failure: keep temp file for retry, `Source` marked failed

Storage utilities in `backend/service/core/storage.py`:

```python
UPLOAD_ROOT = Path(settings.upload_storage_path)

def save_temp_upload(file_data: bytes, original_filename: str) -> str: ...
def move_to_final(temp_path: str, source_id: int, original_filename: str) -> str: ...
def resolve_file_path(relative_path: str) -> Path: ...
```

---

## 4. Parser Details

### 4.1 NoteParser

```python
class NoteParser:
    supported_types = frozenset({"note", "markdown", "text"})

    async def parse(self, source: Source, **kwargs) -> ParseResult:
        text = (source.content or "").strip()
        return ParseResult(text=text)
```

### 4.2 PdfParser

Two-phase extraction:
1. Try `pypdf` text extraction
2. If empty (scanned/image PDF), fallback to OCR:
   - `PyMuPDF` (fitz) render each page to PIL Image
   - `pytesseract.image_to_string()` OCR each page
   - Concatenate results

```python
class PdfParser:
    supported_types = frozenset({"pdf"})

    async def parse(self, source: Source, **kwargs) -> ParseResult:
        file_path = resolve_file_path(source.filename)
        text = self._extract_text(str(file_path))
        if not text.strip():
            text = await self._ocr_pdf(str(file_path))
        if not text.strip():
            raise ValueError("PDF contains no extractable text and OCR produced no results")
        return ParseResult(text=text)
```

### 4.3 ImageParser

Three-phase processing:
1. `Pillow` open image, convert to RGB
2. `pytesseract.image_to_string()` OCR (lang: chi_sim+eng)
3. Vision API description via `HttpxChatCompletionClient`

Output format:
```
[图片文字识别]
{ocr_text}

[图片内容描述]
{vision_description}
```

Vision API integration: Extend `HttpxChatCompletionClient.complete()` to accept `list[dict[str, Any]]` messages (OpenAI vision format with `image_url` content type). The LLM config from `resolve_runtime_llm_config()` is reused.

```python
class ImageParser:
    supported_types = frozenset({"image"})

    def __init__(self, vision_client: HttpxChatCompletionClient | None = None):
        self.vision_client = vision_client

    async def parse(self, source: Source, **kwargs) -> ParseResult:
        file_path = resolve_file_path(source.filename)
        ocr_text = self._ocr_image(str(file_path))
        vision_desc = ""
        if self.vision_client:
            try:
                vision_desc = await self._describe_image(str(file_path))
            except ChatCompletionError:
                pass  # Vision failure is non-fatal

        parts = []
        if ocr_text:
            parts.append(f"[图片文字识别]\n{ocr_text}")
        if vision_desc:
            parts.append(f"[图片内容描述]\n{vision_desc}")

        text = "\n\n".join(parts)
        if not text:
            raise ValueError("Image contains no recognizable text and vision description failed")

        return ParseResult(
            text=text,
            metadata={"ocr_text": ocr_text, "vision_description": vision_desc}
        )
```

**Partial failure tolerance:** OCR fails but Vision succeeds → index vision description. Vision fails but OCR succeeds → index OCR text. Both fail → mark_failed.

### 4.4 DocxParser

```python
class DocxParser:
    supported_types = frozenset({"docx"})

    async def parse(self, source: Source, **kwargs) -> ParseResult:
        from docx import Document
        file_path = resolve_file_path(source.filename)
        doc = Document(str(file_path))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        text = "\n\n".join(paragraphs)
        title = doc.paragraphs[0].text.strip()[:300] if doc.paragraphs else source.title
        return ParseResult(text=text, title=title or None)
```

### 4.5 EpubParser

```python
class EpubParser:
    supported_types = frozenset({"epub"})

    async def parse(self, source: Source, **kwargs) -> ParseResult:
        import ebooklib
        from ebooklib import epub
        file_path = resolve_file_path(source.filename)
        book = epub.read_epub(str(file_path))
        texts = []
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                soup = BeautifulSoup(item.get_content(), "html.parser")
                for tag in soup(["script", "style"]):
                    tag.decompose()
                text = " ".join(soup.get_text(" ").split())
                if text:
                    texts.append(text)
        full_text = "\n\n".join(texts)
        metadata = book.get_metadata("DC", "title")
        title = metadata[0][0] if metadata else source.title
        return ParseResult(text=full_text, title=title or None)
```

### 4.6 WebParser

Supports two modes via `source.source_type`:

**link mode** (simple fetch):
- `httpx.get()` + `BeautifulSoup` text extraction (existing behavior)
- Extract `<title>` tag for title

**web_crawl mode** (recursive with Playwright):
- BFS crawling, same-domain only
- `playwright.async_api` for async page interaction
- Remove nav/header/footer/aside before text extraction
- Configurable `max_depth` (1-3) and `max_pages` (1-50)
- Each page output format: `# {title}\n\n{text}\n\n---\n来源: {url}`
- Concatenate all pages

```python
class WebParser:
    supported_types = frozenset({"link", "web_crawl"})

    def __init__(self, playwright_enabled: bool = True):
        self.playwright_enabled = playwright_enabled

    async def parse(self, source: Source, **kwargs) -> ParseResult:
        if source.source_type == "link":
            return await self._parse_link(source)
        elif source.source_type == "web_crawl":
            max_depth = kwargs.get("max_depth", 1)
            max_pages = kwargs.get("max_pages", 10)
            return await self._parse_crawl(source, max_depth, max_pages)
        else:
            raise ValueError(f"Unsupported web source type: {source.source_type}")
```

**Partial failure tolerance:** Some pages 404/timeout → log warning, continue with successful pages. All pages fail → mark_failed.

### 4.7 BookmarkParser

Parses Netscape HTML bookmark format. Each `<dt><a>` element becomes content.

```python
class BookmarkParser:
    supported_types = frozenset({"bookmark"})

    async def parse(self, source: Source, **kwargs) -> ParseResult:
        soup = BeautifulSoup(source.content or "", "html.parser")
        bookmarks = []
        for dt in soup.find_all("dt"):
            link = dt.find("a")
            if link and link.get("href"):
                title = link.string or ""
                url = link.get("href", "")
                desc = ""
                dd = dt.find_next_sibling("dd")
                if dd and dd.string:
                    desc = dd.string.strip()
                parts = [f"标题: {title}", f"链接: {url}"]
                if desc:
                    parts.append(f"描述: {desc}")
                bookmarks.append("\n".join(parts))
        text = "\n\n---\n\n".join(bookmarks)
        if not text:
            raise ValueError("Invalid bookmark format: no bookmarks found")
        return ParseResult(text=text, metadata={"bookmark_count": len(bookmarks)})
```

**Note:** `bookmark_import` is handled at the API layer, not by a parser. The API parses the uploaded HTML and creates individual `bookmark` sources for each entry.

---

## 5. API Design

### 5.1 Modified Endpoints

**`POST /api/sources/upload`** — Extended multi-file, multi-format upload

```python
@router.post("/upload", response_model=BulkUploadResult)
async def upload_sources(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db)
)
```

Per-file flow:
1. Detect `source_type` from file extension
2. Save to temp path
3. Create `Source` (status=pending, filename=temp_path)
4. Call `get_parser(source_type).parse(source)`
5. On success: move file to final path, update content/title/filename, `mark_indexed`
6. On failure: `mark_failed`
7. Call `KnowledgeService.index_source()` for indexed sources

Supported extensions → source_type mapping:
- `.txt` → `text`
- `.md` → `markdown`
- `.pdf` → `pdf`
- `.docx` → `docx`
- `.epub` → `epub`
- `.png/.jpg/.jpeg/.gif/.webp` → `image`

**`POST /api/sources/{id}/retry`** — Extended to all source types

```python
@router.post("/{source_id}/retry", response_model=SourceDetailRead)
async def retry_source(source_id: int, db: Session = Depends(get_db))
```

Flow:
1. Delete old chunks: `ChunkRepository(db).delete_for_source(source_id)`
2. Call `get_parser(source.source_type).parse(source, **retry_kwargs)`
3. Update content/title
4. `KnowledgeService.index_source(source_id)`

### 5.2 New Endpoints

**`POST /api/sources/crawl`** — Recursive web crawl

```python
@router.post("/crawl", response_model=SourceRead)
async def crawl_source(data: WebCrawlRequest, db: Session = Depends(get_db))
```

Flow:
1. Create `Source` (source_type="web_crawl", url=data.url, status=pending)
2. Call `WebParser.parse(source, max_depth=data.max_depth, max_pages=data.max_pages)`
3. Update content/title, `mark_indexed`
4. `KnowledgeService.index_source(source_id)`

**`POST /api/sources/bookmarks`** — Bookmark batch import

```python
@router.post("/bookmarks", response_model=BulkUploadResult)
async def import_bookmarks(data: BookmarkImportRequest, db: Session = Depends(get_db))
```

Flow:
1. Parse Netscape HTML with BeautifulSoup
2. For each `<dt><a>` bookmark:
   - Create `Source` (source_type="bookmark", url=href, title=text)
   - Attempt to fetch page content via `httpx` + `parse_html`
   - On fetch success: store content, `mark_indexed`, index
   - On fetch failure: store "title + URL" as content, `mark_indexed`, index
3. Return `BulkUploadResult`

---

## 6. Frontend Design

### 6.1 New Types

```typescript
// types.ts
export type SourceType = 'note' | 'markdown' | 'text' | 'pdf' | 'link' | 'image' | 'docx' | 'epub' | 'bookmark' | 'web_crawl'

export interface BulkUploadResult {
  total: number
  succeeded: number
  failed: number
  sources: SourceRead[]
}
```

### 6.2 New API Client Methods

```typescript
// client.ts
uploadSources: (files: File[]) => {
  const body = new FormData()
  files.forEach(f => body.append('files', f))
  return request<BulkUploadResult>('/api/sources/upload', { method: 'POST', body })
},

crawlWeb: (payload: { url: string; max_depth: number; max_pages: number }) =>
  request<SourceRead>('/api/sources/crawl', { method: 'POST', body: JSON.stringify(payload) }),

importBookmarks: (htmlContent: string) =>
  request<BulkUploadResult>('/api/sources/bookmarks', {
    method: 'POST',
    body: JSON.stringify({ html_content: htmlContent })
  }),
```

### 6.3 New Hooks

```typescript
// hooks.ts
export function useUploadSources() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.uploadSources,
    onSuccess: async (result: BulkUploadResult) => {
      for (const source of result.sources) {
        if (source.status === 'pending') await api.indexSource(source.id)
      }
      await queryClient.invalidateQueries({ queryKey: ['sources'] })
      await queryClient.invalidateQueries({ queryKey: ['review'] })
    },
  })
}

export function useCrawlWeb() {
  return useSourceCaptureMutation<{ url: string; max_depth: number; max_pages: number }>(api.crawlWeb)
}

export function useImportBookmarks() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.importBookmarks,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['sources'] })
      await queryClient.invalidateQueries({ queryKey: ['review'] })
    },
  })
}
```

### 6.4 CapturePanel UI Changes

New capture mode type:

```typescript
type CaptureMode = 'note' | 'file' | 'link' | 'bookmarks'
```

**Tab: note** — No changes.

**Tab: file** — Extended:
- `accept`: `.txt,.md,.pdf,.docx,.epub,.png,.jpg,.jpeg,.gif,.webp`
- `multiple`: true (multi-file selection)
- Display file list with upload result summary (succeeded/failed count)

**Tab: link** — Extended:
- URL input (existing)
- "深度抓取" checkbox
- When checked: show `depth` (1-3, default 1) and `max_pages` (5-50, default 10) number inputs
- Submit calls `crawlWeb` instead of `captureLink`

**Tab: bookmarks** (new):
- Textarea for pasting Netscape HTML bookmark content
- Submit button: "导入书签"
- Calls `importBookmarks`
- On success: display import result (total N, succeeded M)

### 6.5 Source Type Icons

Source list and global search results need icon mappings for new types:

| source_type | Icon |
|---|---|
| image | Image icon (Lucide: `Image`) |
| docx | File text icon (Lucide: `FileText`) |
| epub | Book icon (Lucide: `BookOpen`) |
| bookmark | Bookmark icon (Lucide: `Bookmark`) |
| web_crawl | Globe icon (Lucide: `Globe`) |

---

## 7. Error Handling

### 7.1 Parser Error Messages

| Scenario | Error Message | User Action |
|---|---|---|
| Tesseract not installed | `"OCR engine not available: tesseract command not found"` | Install Tesseract, then retry |
| PDF has no text and OCR fails | `"PDF contains no extractable text and OCR failed: {reason}"` | Check PDF quality, then retry |
| Image has no OCR and Vision fails | `"Image contains no recognizable text and vision description failed"` | Image quality too low; no retry needed |
| Vision API call fails | `"Vision description failed: {api_error}"` | Check LLM config, then retry (OCR text still indexed if available) |
| Playwright not installed | `"Web crawl requires Playwright. Install with: playwright install chromium"` | Install, then retry |
| Playwright page timeout | `"Page crawl timed out after 30s: {url}"` | Retry with lower depth/pages |
| DOCX/EPUB parse failure | `"Could not parse file: {reason}"` | Check file integrity, then retry |
| Bookmark HTML invalid | `"Invalid bookmark format: no bookmarks found"` | Check HTML content |

### 7.2 Partial Failure Tolerance

- **Images:** OCR and Vision are independent. Either one succeeding produces indexable content. Both must fail for source to be marked failed.
- **Web crawl:** Individual page failures (404, timeout) are logged as warnings. The crawl continues with successful pages. Only if ALL pages fail is the source marked failed.
- **Bookmark import:** Individual bookmark fetch failures create sources with "title + URL" content (graceful degradation). The overall import reports per-item status in `BulkUploadResult`.

---

## 8. Dependencies

### 8.1 Backend Python Packages

Add to `pyproject.toml`:

```toml
dependencies = [
    # ... existing dependencies ...
    "pytesseract>=0.3.10",      # OCR engine
    "Pillow>=10.0.0",           # Image processing
    "PyMuPDF>=1.23.0",          # PDF rendering for OCR fallback
    "python-docx>=1.1.0",       # Word document parsing
    "ebooklib>=0.18",           # EPUB parsing
    "playwright>=1.40.0",       # Headless browser for web crawl
]
```

### 8.2 System Dependencies

- **Tesseract OCR:**
  - macOS: `brew install tesseract tesseract-lang`
  - Ubuntu/Debian: `apt-get install tesseract-ocr tesseract-ocr-chi-sim`
- **Playwright browsers:** `playwright install chromium`

### 8.3 Frontend

No new npm packages required. All UI changes use existing React/HTML APIs.

---

## 9. Configuration

New settings in `backend/service/config.py`:

```python
class Settings(BaseSettings):
    # ... existing settings ...
    upload_storage_path: str = "data/uploads"
    tesseract_cmd: str | None = None          # Optional: custom tesseract path
    playwright_enabled: bool = True           # Enable/disable Playwright

    model_config = SettingsConfigDict(
        env_prefix="LUMEN_",
        env_file=".env",
        extra="ignore",
    )
```

Environment variables:
- `LUMEN_UPLOAD_STORAGE_PATH` — Upload storage directory (default: `data/uploads`)
- `LUMEN_TESSERACT_CMD` — Custom Tesseract executable path
- `LUMEN_PLAYWRIGHT_ENABLED` — Enable/disable Playwright (default: `true`)

---

## 10. Testing Strategy

### 10.1 Backend Tests

| Test File | Coverage |
|---|---|
| `test_parsers_base.py` | Registry: registration, lookup, unknown type error |
| `test_pdf_parser.py` | Text extraction, scanned PDF OCR fallback, empty PDF failure |
| `test_image_parser.py` | OCR text extraction, vision description (mocked LLM client), merge format |
| `test_docx_parser.py` | Paragraph extraction, title extraction |
| `test_epub_parser.py` | Chapter text extraction, title metadata |
| `test_web_parser.py` | Simple link fetch, Playwright crawl (mocked or test server) |
| `test_bookmark_parser.py` | Netscape HTML parsing, empty content failure |
| `test_sources_api.py` | Multi-file upload, format detection, crawl endpoint, bookmark import, retry all types |

### 10.2 Frontend Tests

Extend `frontend/src/test/workbench.test.tsx`:
- CapturePanel tab switching (4 tabs)
- File input accept attribute and multiple selection
- Deep crawl option toggle and input visibility
- Bookmark textarea and submit flow

---

## 11. Implementation Order

| # | Task | Description |
|---|---|---|
| 1 | Parser infrastructure | `base.py` protocol, `__init__.py` registry, migrate existing `parsing.py` |
| 2 | PDF OCR | `PdfParser` with pypdf + PyMuPDF + Tesseract fallback |
| 3 | Multi-format | `DocxParser` + `EpubParser` |
| 4 | Image knowledge base | `ImageParser` with OCR + Vision description |
| 5 | Web crawl | `WebParser` Playwright recursive crawl |
| 6 | Bookmark import | API endpoint + `BookmarkParser` |
| 7 | Frontend UI | CapturePanel 4 tabs, file multi-select, crawl options, bookmark paste |
| 8 | Integration | End-to-end tests, README update, dependency docs |

Each task is independently testable and can be merged separately.

---

## 12. Rollback / Degradation Plan

- If Tesseract is not installed: PDF/image sources fail with clear error message. Install Tesseract to enable.
- If Playwright is not installed: `web_crawl` falls back to simple link fetch (single page). Set `PLAYWRIGHT_ENABLED=false` to disable gracefully.
- If Vision API is unavailable: Image sources still index OCR text. Vision description is optional enhancement.
- If LLM is not configured: Image sources index OCR text only. Vision description skipped.
