from __future__ import annotations

from pathlib import Path

from langchain_community.document_loaders import BSHTMLLoader, Docx2txtLoader, PyPDFLoader, TextLoader
from langchain_core.documents import Document


def parse_document_file(file_path: str) -> list[Document]:
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return PyPDFLoader(str(path)).load()
    if suffix in {".txt", ".md"}:
        return TextLoader(str(path), encoding="utf-8").load()
    if suffix == ".docx":
        return Docx2txtLoader(str(path)).load()
    if suffix in {".html", ".htm"}:
        return BSHTMLLoader(str(path), open_encoding="utf-8").load()

    raise ValueError(f"Unsupported document type: {suffix or '<none>'}")
