from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_RETRIEVAL_EVAL_PATH = Path("data/eval/retrieval_eval.jsonl")
DEFAULT_ANSWER_EVAL_PATH = Path("data/eval/answer_eval.jsonl")


@dataclass(frozen=True)
class RetrievalEvalSample:
    id: str
    query: str
    category: str
    expected_sources: list[str]
    expected_keywords: list[str]
    expected_min_keyword_hits: int
    answerable: bool
    score_retrieval: bool

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RetrievalEvalSample":
        expected_keywords = [str(keyword) for keyword in payload.get("expected_keywords", [])]
        expected_sources = [str(source) for source in payload.get("expected_sources", [])]
        expected_min_keyword_hits = int(
            payload.get(
                "expected_min_keyword_hits",
                min(2, len(expected_keywords)),
            )
        )
        return cls(
            id=str(payload["id"]),
            query=str(payload["query"]),
            category=str(payload.get("category", "uncategorized")),
            expected_sources=expected_sources,
            expected_keywords=expected_keywords,
            expected_min_keyword_hits=expected_min_keyword_hits,
            answerable=bool(payload.get("answerable", True)),
            score_retrieval=bool(payload.get("score_retrieval", True)),
        )


def load_retrieval_eval_samples(path: str | Path = DEFAULT_RETRIEVAL_EVAL_PATH) -> list[RetrievalEvalSample]:
    dataset_path = Path(path)
    if not dataset_path.exists():
        raise FileNotFoundError(f"Retrieval eval dataset not found: {dataset_path.resolve()}")

    samples: list[RetrievalEvalSample] = []
    with dataset_path.open("r", encoding="utf-8") as fh:
        for line_number, raw_line in enumerate(fh, start=1):
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            try:
                sample = RetrievalEvalSample.from_dict(payload)
            except Exception as exc:  # pragma: no cover - defensive path
                raise ValueError(f"Invalid retrieval eval sample at line {line_number}") from exc
            samples.append(sample)
    return samples


@dataclass(frozen=True)
class AnswerEvalSample:
    id: str
    query: str
    category: str
    expected_facts: list[str]
    expected_min_fact_hits: int
    answerable: bool
    accepted_refusal_keywords: list[str]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AnswerEvalSample":
        expected_facts = [str(fact) for fact in payload.get("expected_facts", [])]
        accepted_refusal_keywords = [
            str(keyword)
            for keyword in payload.get(
                "accepted_refusal_keywords",
                ["不知道", "不确定", "无法确认", "无法判断", "不清楚", "抱歉"],
            )
        ]
        expected_min_fact_hits = int(
            payload.get(
                "expected_min_fact_hits",
                min(2, len(expected_facts)),
            )
        )
        return cls(
            id=str(payload["id"]),
            query=str(payload["query"]),
            category=str(payload.get("category", "uncategorized")),
            expected_facts=expected_facts,
            expected_min_fact_hits=expected_min_fact_hits,
            answerable=bool(payload.get("answerable", True)),
            accepted_refusal_keywords=accepted_refusal_keywords,
        )


def load_answer_eval_samples(path: str | Path = DEFAULT_ANSWER_EVAL_PATH) -> list[AnswerEvalSample]:
    dataset_path = Path(path)
    if not dataset_path.exists():
        raise FileNotFoundError(f"Answer eval dataset not found: {dataset_path.resolve()}")

    samples: list[AnswerEvalSample] = []
    with dataset_path.open("r", encoding="utf-8") as fh:
        for line_number, raw_line in enumerate(fh, start=1):
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            try:
                sample = AnswerEvalSample.from_dict(payload)
            except Exception as exc:  # pragma: no cover - defensive path
                raise ValueError(f"Invalid answer eval sample at line {line_number}") from exc
            samples.append(sample)
    return samples
