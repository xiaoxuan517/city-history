from __future__ import annotations

import logging
from pathlib import Path

from langchain_community.document_loaders import BSHTMLLoader, Docx2txtLoader, PyPDFLoader, TextLoader
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


def _with_document_type(docs: list[Document], document_type: str) -> list[Document]:
    typed_docs: list[Document] = []
    for doc in docs:
        metadata = dict(doc.metadata or {})
        metadata["document_type"] = document_type
        typed_docs.append(
            Document(
                id=getattr(doc, "id", None),
                page_content=doc.page_content,
                metadata=metadata,
            )
        )
    return typed_docs


def load_documents(data_dir: str) -> list[Document]:
    docs: list[Document] = []
    root = Path(data_dir)

    if not root.exists():
        raise FileNotFoundError(f"Data directory not found: {root.resolve()}")

    for path in root.rglob("*"):
        if path.is_dir():
            continue

        suffix = path.suffix.lower()
        if suffix == ".pdf":
            loaded_docs = _with_document_type(PyPDFLoader(str(path)).load(), "pdf")
            docs.extend(loaded_docs)
            logger.info("加载文档。path=%s document_type=pdf docs=%s", path.as_posix(), len(loaded_docs))
            continue

        if suffix == ".txt":
            loaded_docs = _with_document_type(TextLoader(str(path), encoding="utf-8").load(), "text")
            docs.extend(loaded_docs)
            logger.info("加载文档。path=%s document_type=text docs=%s", path.as_posix(), len(loaded_docs))
            continue

        if suffix == ".md":
            loaded_docs = _with_document_type(TextLoader(str(path), encoding="utf-8").load(), "markdown")
            docs.extend(loaded_docs)
            logger.info("加载文档。path=%s document_type=markdown docs=%s", path.as_posix(), len(loaded_docs))
            continue

        if suffix == ".docx":
            loaded_docs = _with_document_type(Docx2txtLoader(str(path)).load(), "docx")
            docs.extend(loaded_docs)
            logger.info("加载文档。path=%s document_type=docx docs=%s", path.as_posix(), len(loaded_docs))
            continue

        if suffix in {".html", ".htm"}:
            loaded_docs = _with_document_type(BSHTMLLoader(str(path), open_encoding="utf-8").load(), "html")
            docs.extend(loaded_docs)
            logger.info("加载文档。path=%s document_type=html docs=%s", path.as_posix(), len(loaded_docs))
            continue

        logger.debug("跳过不支持的文件。path=%s suffix=%s", path.as_posix(), suffix)

    logger.info("原始文档加载完成。data_dir=%s 文档数=%s", root.resolve(), len(docs))
    return docs
