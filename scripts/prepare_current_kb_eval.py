from __future__ import annotations

import argparse
import mimetypes
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select

from app.db.models.knowledge_base import KnowledgeBase
from app.db.models.user import User
from app.db.session import get_session_factory
from app.schemas.auth import UserCreate
from app.schemas.knowledge_base import KnowledgeBaseCreate
from app.services.auth_service import AuthError, AuthService
from app.services.document_service import DocumentService
from app.services.kb_service import KnowledgeBaseService
from evaluation.dataset import load_retrieval_eval_samples


DEFAULT_USERNAME = "eval_user"
DEFAULT_EMAIL = "eval@example.com"
DEFAULT_PASSWORD = "eval-password-123"
DEFAULT_KB_NAME = "current-kb-eval"
DEFAULT_RAW_DIR = Path("data/raw")
DEFAULT_RETRIEVAL_DATASET = Path("data/eval/current_kb_retrieval.jsonl")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare the local current_kb eval knowledge base.")
    parser.add_argument("--raw-dir", default=str(DEFAULT_RAW_DIR), help="Directory containing source documents.")
    parser.add_argument(
        "--retrieval-dataset",
        default=str(DEFAULT_RETRIEVAL_DATASET),
        help="Retrieval dataset used to discover expected source files.",
    )
    parser.add_argument("--username", default=DEFAULT_USERNAME, help="Eval user username.")
    parser.add_argument("--email", default=DEFAULT_EMAIL, help="Eval user email.")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Eval user password.")
    parser.add_argument("--kb-name", default=DEFAULT_KB_NAME, help="Eval knowledge base name.")
    parser.add_argument(
        "--list-sources",
        action="store_true",
        help="Only list expected source files and validate they exist; do not connect to the database.",
    )
    parser.add_argument(
        "--force-reupload",
        action="store_true",
        help="Upload and process documents even when the KB already has a document with the same filename.",
    )
    return parser.parse_args()


def _get_or_create_user(session, *, username: str, email: str, password: str) -> User:
    auth_service = AuthService()
    existing = session.scalar(select(User).where(User.username == username.strip().lower()))
    if existing is not None:
        return existing
    try:
        return auth_service.register(
            session,
            UserCreate(username=username, email=email, password=password),
        )
    except AuthError:
        existing = session.scalar(select(User).where(User.email == email.strip().lower()))
        if existing is None:
            raise
        return existing


def _get_or_create_kb(session, *, user_id: int, name: str) -> KnowledgeBase:
    existing = session.scalar(
        select(KnowledgeBase).where(KnowledgeBase.user_id == user_id, KnowledgeBase.name == name)
    )
    if existing is not None:
        return existing
    return KnowledgeBaseService().create(
        session,
        user_id=user_id,
        payload=KnowledgeBaseCreate(name=name, description="Local eval knowledge base generated from data/raw."),
    )


def _expected_source_names(dataset_path: Path) -> list[str]:
    names: set[str] = set()
    for sample in load_retrieval_eval_samples(dataset_path):
        names.update(sample.expected_sources)
    return sorted(name for name in names if name)


def _content_type_for(path: Path) -> str:
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def main() -> None:
    args = _parse_args()
    raw_dir = Path(args.raw_dir)
    dataset_path = Path(args.retrieval_dataset)
    expected_sources = _expected_source_names(dataset_path)
    if not expected_sources:
        raise SystemExit(f"No expected sources found in {dataset_path}")

    missing = [source for source in expected_sources if not (raw_dir / source).exists()]
    if missing:
        raise SystemExit(f"Missing source files under {raw_dir}: {missing}")
    if args.list_sources:
        print(f"source_count={len(expected_sources)}")
        for source in expected_sources:
            print(f"source={source}")
        return

    session_factory = get_session_factory()
    document_service = DocumentService()
    with session_factory() as session:
        user = _get_or_create_user(
            session,
            username=args.username,
            email=args.email,
            password=args.password,
        )
        kb = _get_or_create_kb(session, user_id=user.id, name=args.kb_name)
        existing_documents = {
            document.filename
            for document in document_service.list_for_kb(session, user_id=user.id, kb_id=kb.id)
        }

        processed: list[tuple[str, int, int]] = []
        skipped: list[str] = []
        for source in expected_sources:
            if source in existing_documents and not args.force_reupload:
                skipped.append(source)
                continue
            source_path = raw_dir / source
            document = document_service.create_upload(
                session,
                user_id=user.id,
                kb_id=kb.id,
                filename=source_path.name,
                content_type=_content_type_for(source_path),
                content=source_path.read_bytes(),
            )
            processed_document, chunk_count = document_service.process_sync(
                session,
                user_id=user.id,
                document_id=document.id,
            )
            processed.append((processed_document.filename, processed_document.id, chunk_count))

    print(f"user_id={user.id}")
    print(f"kb_id={kb.id}")
    if skipped:
        print(f"skipped_existing={','.join(skipped)}")
    for filename, document_id, chunk_count in processed:
        print(f"processed filename={filename} document_id={document_id} chunk_count={chunk_count}")
    print(
        "baseline_command=uv run python -m evaluation.run_pgvector_baseline "
        f"--user-id {user.id} --kb-id {kb.id} "
        "--retrieval-dataset data/eval/current_kb_retrieval.jsonl "
        "--answer-dataset data/eval/current_kb_answer.jsonl "
        "--retrieval-limit 10 --answer-limit 5"
    )


if __name__ == "__main__":
    main()
