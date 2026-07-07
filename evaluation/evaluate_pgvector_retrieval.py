from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config.logging_setup import setup_logging
from app.config.settings import settings
from app.db.session import get_session_factory
from app.retrieval.pgvector_store import retrieve_pgvector_retrieved_chunks
from app.retrieval.types import RetrievedChunk
from evaluation.dataset import DEFAULT_RETRIEVAL_EVAL_PATH, RetrievalEvalSample, load_retrieval_eval_samples


@dataclass(frozen=True)
class PgVectorRetrievalEvalConfig:
    user_id: int
    kb_id: int
    top_k: int
    search_type: str
    fetch_k: int
    reranker_enabled: bool

    @property
    def label(self) -> str:
        reranker = "on" if self.reranker_enabled else "off"
        return (
            f"user_id={self.user_id} kb_id={self.kb_id} "
            f"search_type={self.search_type} top_k={self.top_k} fetch_k={self.fetch_k} reranker={reranker}"
        )


@dataclass(frozen=True)
class PgVectorRetrievalEvalResult:
    sample: RetrievalEvalSample
    config: PgVectorRetrievalEvalConfig
    skipped: bool
    passed: bool
    source_hit: bool
    permission_ok: bool
    hit_ranks: list[int]
    matched_keywords: list[str]
    required_keyword_hits: int
    chunks: list[RetrievedChunk]


def evaluate_pgvector_sample(
    sample: RetrievalEvalSample,
    config: PgVectorRetrievalEvalConfig,
    chunks: list[RetrievedChunk],
) -> PgVectorRetrievalEvalResult:
    permission_ok = all(
        chunk.metadata.get("user_id") == config.user_id
        and chunk.metadata.get("kb_id") == config.kb_id
        for chunk in chunks
    )
    if not sample.score_retrieval:
        return PgVectorRetrievalEvalResult(
            sample=sample,
            config=config,
            skipped=True,
            passed=False,
            source_hit=False,
            permission_ok=permission_ok,
            hit_ranks=[],
            matched_keywords=[],
            required_keyword_hits=sample.expected_min_keyword_hits,
            chunks=chunks,
        )

    hit_ranks = [chunk.rank or 0 for chunk in chunks if chunk.source in sample.expected_sources]
    matched_keywords = _match_keywords(sample, chunks)
    source_hit = bool(hit_ranks)
    passed = permission_ok and source_hit and len(matched_keywords) >= sample.expected_min_keyword_hits
    return PgVectorRetrievalEvalResult(
        sample=sample,
        config=config,
        skipped=False,
        passed=passed,
        source_hit=source_hit,
        permission_ok=permission_ok,
        hit_ranks=hit_ranks,
        matched_keywords=matched_keywords,
        required_keyword_hits=sample.expected_min_keyword_hits,
        chunks=chunks,
    )


def result_to_bad_case(result: PgVectorRetrievalEvalResult) -> dict[str, Any]:
    return {
        "id": result.sample.id,
        "query": result.sample.query,
        "category": result.sample.category,
        "config": {
            "user_id": result.config.user_id,
            "kb_id": result.config.kb_id,
            "search_type": result.config.search_type,
            "top_k": result.config.top_k,
            "fetch_k": result.config.fetch_k,
            "reranker_enabled": result.config.reranker_enabled,
        },
        "expected_sources": result.sample.expected_sources,
        "expected_keywords": result.sample.expected_keywords,
        "source_hit": result.source_hit,
        "permission_ok": result.permission_ok,
        "matched_keywords": result.matched_keywords,
        "required_keyword_hits": result.required_keyword_hits,
        "references": [chunk.to_reference() for chunk in result.chunks],
    }


def summarize(results: list[PgVectorRetrievalEvalResult]) -> dict[str, float | int]:
    scored_results = [result for result in results if not result.skipped]
    source_hits = [result for result in scored_results if result.source_hit]
    permission_passes = [result for result in scored_results if result.permission_ok]
    passed_results = [result for result in scored_results if result.passed]
    return {
        "total": len(results),
        "scored": len(scored_results),
        "skipped": len(results) - len(scored_results),
        "source_hit": len(source_hits),
        "permission_ok": len(permission_passes),
        "passed": len(passed_results),
        "source_hit_rate": round(len(source_hits) / len(scored_results), 4) if scored_results else 0.0,
        "permission_ok_rate": round(len(permission_passes) / len(scored_results), 4) if scored_results else 0.0,
        "pass_rate": round(len(passed_results) / len(scored_results), 4) if scored_results else 0.0,
    }


def _match_keywords(sample: RetrievalEvalSample, chunks: list[RetrievedChunk]) -> list[str]:
    corpus = "\n".join(chunk.content.lower() for chunk in chunks)
    return [keyword for keyword in sample.expected_keywords if keyword.lower() in corpus]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run retrieval evaluation against PostgreSQL + pgvector.")
    parser.add_argument("--dataset", default=str(DEFAULT_RETRIEVAL_EVAL_PATH), help="Path to retrieval eval jsonl.")
    parser.add_argument("--user-id", type=int, required=True, help="Tenant user id used for SQL permission filter.")
    parser.add_argument("--kb-id", type=int, required=True, help="Knowledge base id used for SQL permission filter.")
    parser.add_argument(
        "--search-type",
        nargs="+",
        default=["similarity"],
        choices=["similarity", "hybrid"],
        help="pgvector retrieval modes to compare.",
    )
    parser.add_argument("--top-k", type=int, default=settings.top_k, help="Number of chunks to retrieve.")
    parser.add_argument("--fetch-k", type=int, default=settings.retrieval_fetch_k, help="Candidate count for hybrid.")
    parser.add_argument(
        "--reranker",
        nargs="+",
        default=["off"],
        choices=["off", "on"],
        help="Compare pgvector retrieval with reranker disabled/enabled.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Only evaluate the first N samples.")
    parser.add_argument("--show-passes", action="store_true", help="Print passing samples as well.")
    parser.add_argument("--bad-cases-out", default=None, help="Optional JSONL output for failed samples.")
    parser.add_argument("--manifest-output", default=None, help="Optional path to write an eval run manifest JSON.")
    return parser.parse_args()


def _print_result(result: PgVectorRetrievalEvalResult) -> None:
    if result.skipped:
        status = "SKIP"
    elif result.passed:
        status = "PASS"
    else:
        status = "FAIL"

    print(f"[{status}] {result.sample.id} | {result.sample.query}")
    print(f"  expected_sources={result.sample.expected_sources or ['<none>']}")
    print(f"  retrieved_sources={[chunk.source for chunk in result.chunks]}")
    print(
        "  permission_ok=%s source_hit=%s hit_ranks=%s keywords=%s/%s matched=%s"
        % (
            result.permission_ok,
            result.source_hit,
            result.hit_ranks,
            len(result.matched_keywords),
            result.required_keyword_hits,
            result.matched_keywords,
        )
    )


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def _write_bad_cases(path: str | Path, results: list[PgVectorRetrievalEvalResult]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        for result in results:
            if result.skipped or result.passed:
                continue
            fh.write(json.dumps(result_to_bad_case(result), ensure_ascii=False) + "\n")


def _write_manifest(
    path: str | Path,
    *,
    args: argparse.Namespace,
    config: PgVectorRetrievalEvalConfig,
    summary: dict[str, Any],
    sample_count: int,
) -> None:
    created_at = datetime.now(UTC)
    _write_json(
        path,
        {
            "run_id": created_at.strftime("%Y%m%dT%H%M%SZ"),
            "created_at": created_at.isoformat(),
            "dataset": str(Path(args.dataset)),
            "sample_count": sample_count,
            "limit": args.limit,
            "backend": "pgvector",
            "models": {"embedding_model": settings.embedding_model},
            "config": {
                "label": config.label,
                "user_id": config.user_id,
                "kb_id": config.kb_id,
                "search_type": config.search_type,
                "top_k": config.top_k,
                "fetch_k": config.fetch_k,
                "reranker_enabled": config.reranker_enabled,
            },
            "summary": summary,
        },
    )


def main() -> None:
    args = _parse_args()
    setup_logging()

    samples = load_retrieval_eval_samples(Path(args.dataset))
    if args.limit is not None:
        samples = samples[: args.limit]

    session_factory = get_session_factory()
    all_results: list[PgVectorRetrievalEvalResult] = []
    for search_type in args.search_type:
        for reranker_mode in args.reranker:
            reranker_enabled = reranker_mode == "on"
            config = PgVectorRetrievalEvalConfig(
                user_id=args.user_id,
                kb_id=args.kb_id,
                top_k=args.top_k,
                search_type=search_type,
                fetch_k=max(args.fetch_k, args.top_k),
                reranker_enabled=reranker_enabled,
            )
            with session_factory() as session:
                results = [
                    evaluate_pgvector_sample(
                        sample,
                        config,
                        retrieve_pgvector_retrieved_chunks(
                            session,
                            user_id=config.user_id,
                            kb_id=config.kb_id,
                            query=sample.query,
                            top_k=config.top_k,
                            search_type=config.search_type,
                            fetch_k=config.fetch_k,
                            reranker_enabled=config.reranker_enabled,
                        ),
                    )
                    for sample in samples
                ]

            all_results.extend(results)
            summary = summarize(results)
            print(f"\n=== PgVector Retrieval Eval | {config.label} ===")
            print(
                "summary total={total} scored={scored} skipped={skipped} "
                "source_hit={source_hit} source_hit_rate={source_hit_rate:.2%} "
                "permission_ok={permission_ok} permission_ok_rate={permission_ok_rate:.2%} "
                "passed={passed} pass_rate={pass_rate:.2%}".format(**summary)
            )
            for result in results:
                if result.passed and not args.show_passes:
                    continue
                _print_result(result)

            if args.manifest_output:
                output_path = Path(args.manifest_output)
                suffix = f"{search_type}_reranker_{reranker_mode}"
                manifest_path = output_path.with_name(f"{output_path.stem}_{suffix}{output_path.suffix}")
                _write_manifest(
                    manifest_path,
                    args=args,
                    config=config,
                    summary=summary,
                    sample_count=len(samples),
                )
                print(f"manifest_written={manifest_path.as_posix()}")

    if args.bad_cases_out:
        _write_bad_cases(args.bad_cases_out, all_results)
        print(f"bad_cases_written={Path(args.bad_cases_out).as_posix()}")


if __name__ == "__main__":
    main()
