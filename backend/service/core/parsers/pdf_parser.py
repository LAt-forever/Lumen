from pypdf import PdfReader

from service.core.parsers.base import ParseResult
from service.core.storage import resolve_file_path

# Optional OCR dependencies — gracefully degrade if missing
try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover
    fitz = None  # type: ignore[assignment]

try:
    import pytesseract
    from PIL import Image
except Exception:  # pragma: no cover
    pytesseract = None  # type: ignore[assignment]
    Image = None  # type: ignore[assignment]


class PdfParser:
    supported_types = frozenset({"pdf"})

    async def parse(self, source, **kwargs) -> ParseResult:
        if not source.filename:
            raise ValueError("PDF source is missing filename")

        file_path = resolve_file_path(source.filename)
        reader = PdfReader(str(file_path))

        # Phase 1: Extract text with pypdf
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n\n".join(page.strip() for page in pages if page.strip())

        # Phase 2: OCR fallback for scanned/image PDFs
        if not text.strip():
            text = await self._ocr_pdf(file_path)

        if not text.strip():
            raise ValueError(
                "PDF contains no extractable text and OCR produced no results"
            )

        return ParseResult(text=text.strip())

    async def _ocr_pdf(self, file_path) -> str:
        if fitz is None or pytesseract is None or Image is None:
            return ""

        doc = fitz.open(str(file_path))
        ocr_pages: list[str] = []
        try:
            for page in doc:
                # Render page at 200 DPI
                mat = fitz.Matrix(200 / 72, 200 / 72)
                pix = page.get_pixmap(matrix=mat)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                page_text = pytesseract.image_to_string(img, lang="chi_sim+eng")
                if page_text.strip():
                    ocr_pages.append(page_text.strip())
        finally:
            doc.close()

        return "\n\n".join(ocr_pages)
