from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.retrieval.embeddings import get_embeddings


@dataclass(frozen=True)
class PgVectorEmbeddingCheck:
    embedding_model: str
    configured_dimension: int
    database_dimension: int | None
    actual_dimension: int | None
    chunk_count: int
    database_error: str | None
    ok: bool
    issues: list[str]


def check_pgvector_embedding_config(*, probe_model: bool = False) -> PgVectorEmbeddingCheck:
    database_error = None
    try:
        database_dimension = _get_database_embedding_dimension()
        chunk_count = _get_chunk_count()
    except RuntimeError as exc:
        database_dimension = None
        chunk_count = 0
        database_error = str(exc)

    actual_dimension = _get_actual_embedding_dimension() if probe_model else None
    issues = _collect_issues(
        configured_dimension=settings.embedding_dimension,
        database_dimension=database_dimension,
        actual_dimension=actual_dimension,
    )
    if database_error is not None:
        issues.append(f"Database check failed: {database_error}")
    return PgVectorEmbeddingCheck(
        embedding_model=settings.embedding_model,
        configured_dimension=settings.embedding_dimension,
        database_dimension=database_dimension,
        actual_dimension=actual_dimension,
        chunk_count=chunk_count,
        database_error=database_error,
        ok=not issues,
        issues=issues,
    )


def _collect_issues(
    *,
    configured_dimension: int,
    database_dimension: int | None,
    actual_dimension: int | None,
) -> list[str]:
    issues: list[str] = []
    if database_dimension is None:
        issues.append("Could not detect document_chunks.embedding vector dimension.")
    elif database_dimension != configured_dimension:
        issues.append(
            f"Database vector dimension {database_dimension} does not match EMBEDDING_DIMENSION {configured_dimension}."
        )

    if actual_dimension is not None and actual_dimension != configured_dimension:
        issues.append(
            f"Actual embedding model output dimension {actual_dimension} does not match EMBEDDING_DIMENSION {configured_dimension}."
        )
    return issues


def _get_database_embedding_dimension() -> int | None:
    statement = text(
        """
        select atttypmod
        from pg_attribute
        where attrelid = 'document_chunks'::regclass
          and attname = 'embedding'
          and not attisdropped
        """
    )
    typmod = _scalar(statement)
    if typmod is None or typmod < 0:
        return None
    return int(typmod)


def _get_chunk_count() -> int:
    return int(_scalar(text("select count(*) from document_chunks")) or 0)


def _scalar(statement) -> Any:
    connect_args: dict[str, Any] = {}
    if settings.database_url.startswith("postgresql"):
        connect_args["connect_timeout"] = 5

    engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=connect_args)
    try:
        with Session(engine) as session:
            return session.scalar(statement)
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc
    finally:
        engine.dispose()


def _get_actual_embedding_dimension() -> int:
    vector = get_embeddings().embed_query("dimension check")
    return len(vector)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check pgvector embedding dimension configuration.")
    parser.add_argument(
        "--probe-model",
        action="store_true",
        help="Call the embedding model and compare its real output dimension.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args()


def _print_human(check: PgVectorEmbeddingCheck) -> None:
    print(f"embedding_model={check.embedding_model}")
    print(f"configured_dimension={check.configured_dimension}")
    print(f"database_dimension={check.database_dimension}")
    print(f"actual_dimension={check.actual_dimension}")
    print(f"chunk_count={check.chunk_count}")
    print(f"database_error={check.database_error}")
    print(f"ok={str(check.ok).lower()}")
    for issue in check.issues:
        print(f"issue={issue}")


def main() -> None:
    args = _parse_args()
    check = check_pgvector_embedding_config(probe_model=args.probe_model)
    if args.json:
        print(json.dumps(asdict(check), ensure_ascii=False, indent=2))
        return
    _print_human(check)


if __name__ == "__main__":
    main()
