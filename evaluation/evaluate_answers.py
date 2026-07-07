from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from evaluation.dataset import DEFAULT_ANSWER_EVAL_PATH, AnswerEvalSample, load_answer_eval_samples

DEFAULT_RUNS_PATH = Path("storage/exports/answer_eval_runs.jsonl")
DEFAULT_BAD_CASES_PATH = Path("data/eval/bad_cases.jsonl")
AnswerGrade = Literal["correct", "partial", "acceptable_refusal", "hallucination"]


@dataclass(frozen=True)
class AnswerRun:
    id: str
    query: str
    category: str
    answer: str
    elapsed_ms: int | None
    usage: dict[str, Any] | None
    metadata: dict[str, Any]


@dataclass(frozen=True)
class AnswerEvalResult:
    sample: AnswerEvalSample
    run: AnswerRun
    grade: AnswerGrade
    passed: bool
    matched_facts: list[str]
    required_fact_hits: int
    refusal_detected: bool


def _normalize_text(text: str) -> str:
    return text.strip().lower()


def _contains_refusal(answer: str, accepted_refusal_keywords: list[str]) -> bool:
    normalized = _normalize_text(answer)
    return any(keyword.lower() in normalized for keyword in accepted_refusal_keywords)


def _match_facts(sample: AnswerEvalSample, answer: str) -> list[str]:
    normalized_answer = _normalize_text(answer)
    return [fact for fact in sample.expected_facts if fact.lower() in normalized_answer]


def _grade_answer(sample: AnswerEvalSample, answer: str) -> tuple[AnswerGrade, list[str], bool]:
    matched_facts = _match_facts(sample, answer)
    refusal_detected = _contains_refusal(answer, sample.accepted_refusal_keywords)

    if not sample.answerable:
        if refusal_detected:
            return "acceptable_refusal", matched_facts, refusal_detected
        return "hallucination", matched_facts, refusal_detected

    if len(matched_facts) >= sample.expected_min_fact_hits:
        return "correct", matched_facts, refusal_detected
    if refusal_detected:
        return "acceptable_refusal", matched_facts, refusal_detected
    if matched_facts:
        return "partial", matched_facts, refusal_detected
    return "hallucination", matched_facts, refusal_detected


def _load_runs(path: str | Path) -> dict[str, AnswerRun]:
    runs_path = Path(path)
    if not runs_path.exists():
        raise FileNotFoundError(f"Answer eval run file not found: {runs_path.resolve()}")

    runs: dict[str, AnswerRun] = {}
    with runs_path.open("r", encoding="utf-8") as fh:
        for line_number, raw_line in enumerate(fh, start=1):
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            try:
                run = AnswerRun(
                    id=str(payload["id"]),
                    query=str(payload["query"]),
                    category=str(payload.get("category", "uncategorized")),
                    answer=str(payload["answer"]),
                    elapsed_ms=payload.get("elapsed_ms"),
                    usage=payload.get("usage"),
                    metadata={
                        key: value
                        for key, value in payload.items()
                        if key not in {"id", "query", "category", "answer", "elapsed_ms", "usage"}
                    },
                )
            except Exception as exc:  # pragma: no cover - defensive path
                raise ValueError(f"Invalid answer eval run at line {line_number}") from exc
            runs[run.id] = run
    return runs


def evaluate_answers(samples: list[AnswerEvalSample], runs: dict[str, AnswerRun]) -> list[AnswerEvalResult]:
    results: list[AnswerEvalResult] = []
    for sample in samples:
        run = runs.get(sample.id)
        if run is None:
            raise KeyError(f"Missing answer run for sample: {sample.id}")
        grade, matched_facts, refusal_detected = _grade_answer(sample, run.answer)
        passed = grade == "correct" or (not sample.answerable and grade == "acceptable_refusal")
        results.append(
            AnswerEvalResult(
                sample=sample,
                run=run,
                grade=grade,
                passed=passed,
                matched_facts=matched_facts,
                required_fact_hits=sample.expected_min_fact_hits,
                refusal_detected=refusal_detected,
            )
        )
    return results


def _summarize(results: list[AnswerEvalResult]) -> dict[str, int | float]:
    total = len(results)
    grade_counts = {
        "correct": 0,
        "partial": 0,
        "acceptable_refusal": 0,
        "hallucination": 0,
    }
    for result in results:
        grade_counts[result.grade] += 1

    passed = sum(1 for result in results if result.passed)
    return {
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        **grade_counts,
    }


def _print_result(result: AnswerEvalResult) -> None:
    print(f"[{result.grade.upper()}] {result.sample.id} | {result.sample.query}")
    print(f"  category={result.sample.category}")
    print(
        "  facts=%s/%s matched=%s refusal=%s"
        % (
            len(result.matched_facts),
            result.required_fact_hits,
            result.matched_facts,
            result.refusal_detected,
        )
    )
    print(f"  answer={result.run.answer}")


def _write_bad_cases(path: str | Path, results: list[AnswerEvalResult]) -> None:
    bad_case_path = Path(path)
    bad_case_path.parent.mkdir(parents=True, exist_ok=True)
    with bad_case_path.open("w", encoding="utf-8") as fh:
        for result in results:
            if result.passed:
                continue
            payload = {
                "id": result.sample.id,
                "query": result.sample.query,
                "category": result.sample.category,
                "grade": result.grade,
                "matched_facts": result.matched_facts,
                "required_fact_hits": result.required_fact_hits,
                "refusal_detected": result.refusal_detected,
                "answer": result.run.answer,
                "run_metadata": result.run.metadata,
            }
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate sampled answers with rule-based grading.")
    parser.add_argument("--dataset", default=str(DEFAULT_ANSWER_EVAL_PATH), help="Path to answer eval jsonl.")
    parser.add_argument("--runs", default=str(DEFAULT_RUNS_PATH), help="Path to sampled answer run jsonl.")
    parser.add_argument("--limit", type=int, default=None, help="Only evaluate the first N samples.")
    parser.add_argument("--show-passes", action="store_true", help="Print passing samples as well.")
    parser.add_argument(
        "--bad-cases-out",
        default=str(DEFAULT_BAD_CASES_PATH),
        help="Path to export failed answer cases as jsonl.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    samples = load_answer_eval_samples(Path(args.dataset))
    if args.limit is not None:
        samples = samples[: args.limit]

    runs = _load_runs(Path(args.runs))
    results = evaluate_answers(samples, runs)
    summary = _summarize(results)

    print(
        "summary total={total} passed={passed} pass_rate={pass_rate:.2%} "
        "correct={correct} partial={partial} acceptable_refusal={acceptable_refusal} "
        "hallucination={hallucination}".format(**summary)
    )

    for result in results:
        if result.passed and not args.show_passes:
            continue
        _print_result(result)

    _write_bad_cases(args.bad_cases_out, results)
    print(f"bad_cases_written={Path(args.bad_cases_out).as_posix()}")


if __name__ == "__main__":
    main()
