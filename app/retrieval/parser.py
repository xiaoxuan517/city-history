from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from langchain_community.document_loaders import BSHTMLLoader, Docx2txtLoader, PyPDFLoader, TextLoader
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


def parse_document_file(file_path: str) -> list[Document]:
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return _load_pdf_with_ocr_fallback(path)
    if suffix in {".txt", ".md"}:
        return TextLoader(str(path), encoding="utf-8").load()
    if suffix == ".docx":
        return Docx2txtLoader(str(path)).load()
    if suffix in {".html", ".htm"}:
        return BSHTMLLoader(str(path), open_encoding="utf-8").load()

    raise ValueError(f"Unsupported document type: {suffix or '<none>'}")


def _load_pdf_with_ocr_fallback(path: Path) -> list[Document]:
    docs = PyPDFLoader(str(path)).load()
    empty_docs = [doc for doc in docs if not doc.page_content.strip()]
    if not empty_docs:
        return docs

    logger.info("PDF 存在空文本页，开始 OCR 兜底。path=%s empty_pages=%s", path, len(empty_docs))
    for index, doc in enumerate(docs):
        if doc.page_content.strip():
            continue
        page_number = _page_number(doc, fallback=index)
        ocr_text = _ocr_pdf_page(path, page_number)
        if ocr_text:
            doc.page_content = ocr_text
            doc.metadata = {**doc.metadata, "ocr": True}
    return docs


def _page_number(doc: Document, *, fallback: int) -> int:
    raw_page = doc.metadata.get("page")
    return raw_page if isinstance(raw_page, int) and raw_page >= 0 else fallback


def _ocr_pdf_page(path: Path, page_number: int) -> str:
    try:
        import fitz
        import numpy as np
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "PDF OCR fallback requires pymupdf, pillow, numpy, and rapidocr-onnxruntime dependencies."
        ) from exc

    with fitz.open(path) as pdf:
        if page_number >= pdf.page_count:
            return ""
        page = pdf.load_page(page_number)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)

    result, _ = _ocr_engine()(np.asarray(image))
    return "\n".join(_ocr_text_lines(result))


@lru_cache(maxsize=1)
def _ocr_engine():
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as exc:
        raise RuntimeError("PDF OCR fallback requires rapidocr-onnxruntime dependency.") from exc
    return RapidOCR()


def _ocr_text_lines(result) -> list[str]:
    lines: list[str] = []
    for item in result or []:
        text = ""
        if isinstance(item, (list, tuple)) and len(item) >= 3:
            text = str(item[1] or "").strip()
        elif isinstance(item, (list, tuple)) and len(item) >= 2 and isinstance(item[1], (list, tuple)):
            text = str(item[1][0] or "").strip()
        if text:
            lines.append(text)
    return lines
