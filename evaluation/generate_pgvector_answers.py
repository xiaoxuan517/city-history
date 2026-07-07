from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Protocol

from sqlalchemy.orm import Session

from app.config.logging_setup import setup_logging
from app.db.session import get_session_factory
from app.services.chat_service import ChatAnswer, ChatService, get_chat_service
from evaluation.dataset import DEFAULT_ANSWER_EVAL_PATH, AnswerEvalSample, load_answer_eval_samples

DEFAULT_OUTPUT_PATH = Path("storage/exports/pgvector_answer_eval_runs.jsonl")


class ChatServiceLike(Protocol):
    def ask(
        self,
        session: Session,
        *,
        user_id: int,
        kb_id: int,
        question: str,
        session_id: int | None = None,
    ) -> ChatAnswer:
        ...


@dataclass(frozen=True)
class PgVectorAnswerRunConfig:
    user_id: int
    kb_id: int


def build_answer_run_record(
    sample: AnswerEvalSample,
    answer: ChatAnswer,
    *,
    config: PgVectorAnswerRunConfig,
    elapsed_ms: int,
) -> dict:
    return {
        "id": sample.id,
        "query": sample.query,
        "category": sample.category,
        "backend": "pgvector",
        "user_id": config.user_id,
        "kb_id": config.kb_id,
        "session_id": answer.session_id,
        "run_id": answer.run_id,
        "answer": answer.answer,
        "references": answer.references,
        "elapsed_ms": elapsed_ms,
        "usage": answer.usage,
        "cache_hit": answer.cache_hit,
    }


def generate_pgvector_answer_runs(
    samples: list[AnswerEvalSample],
    *,
    session: Session,
    chat_service: ChatServiceLike,
    config: PgVectorAnswerRunConfig,
) -> list[dict]:
    records: list[dict] = []
    for sample in samples:
        started_at = perf_counter()
        answer = chat_service.ask(
            session,
            user_id=config.user_id,
            kb_id=config.kb_id,
            question=sample.query,
        )
        elapsed_ms = int((perf_counter() - started_at) * 1000)
        records.append(
            build_answer_run_record(
                sample,
                answer,
                config=config,
                elapsed_ms=elapsed_ms,
            )
        )
    return records


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sample pgvector chat answers for the answer eval dataset.")
    parser.add_argument("--dataset", default=str(DEFAULT_ANSWER_EVAL_PATH), help="Path to answer eval jsonl.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH), help="Path to output run jsonl.")
    parser.add_argument("--user-id", type=int, required=True, help="Tenant user id used for chat service.")
    parser.add_argument("--kb-id", type=int, required=True, help="Knowledge base id used for chat service.")
    parser.add_argument("--limit", type=int, default=None, help="Only run the first N samples.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    setup_logging()

    samples = load_answer_eval_samples(Path(args.dataset))
    if args.limit is not None:
        samples = samples[: args.limit]

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    config = PgVectorAnswerRunConfig(user_id=args.user_id, kb_id=args.kb_id)
    session_factory = get_session_factory()
    chat_service = get_chat_service()

    with session_factory() as session:
        records = generate_pgvector_answer_runs(
            samples,
            session=session,
            chat_service=chat_service,
            config=config,
        )

    with output_path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(f"[OK] {record['id']} -> {output_path.as_posix()}")


if __name__ == "__main__":
    main()
