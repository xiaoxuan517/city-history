from __future__ import annotations

import argparse
import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class SmokeConfig:
    base_url: str
    username: str
    email: str
    password: str
    poll_seconds: int
    request_timeout: int
    skip_chat: bool
    sync_fallback: bool


class SmokeClient:
    def __init__(self, base_url: str, *, request_timeout: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.request_timeout = request_timeout
        self.token: str | None = None

    def get(self, path: str) -> Any:
        return self._request("GET", path)

    def post_json(self, path: str, payload: dict[str, Any]) -> Any:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        return self._request("POST", path, body=body, content_type="application/json")

    def delete(self, path: str) -> None:
        self._request("DELETE", path)

    def upload_file(self, path: str, *, field_name: str, filename: str, content: bytes, content_type: str) -> Any:
        boundary = f"----smoke-{uuid.uuid4().hex}"
        body = _multipart_body(
            boundary=boundary,
            field_name=field_name,
            filename=filename,
            content=content,
            content_type=content_type,
        )
        return self._request("POST", path, body=body, content_type=f"multipart/form-data; boundary={boundary}")

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None = None,
        content_type: str | None = None,
    ) -> Any:
        headers = {"Accept": "application/json"}
        if content_type:
            headers["Content-Type"] = content_type
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        request = Request(
            f"{self.base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=self.request_timeout) as response:
                data = response.read()
                if not data:
                    return None
                return json.loads(data.decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{method} {path} failed with HTTP {exc.code}: {detail}") from exc


def _multipart_body(
    *,
    boundary: str,
    field_name: str,
    filename: str,
    content: bytes,
    content_type: str,
) -> bytes:
    lines = [
        f"--{boundary}",
        f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"',
        f"Content-Type: {content_type}",
        "",
    ]
    head = "\r\n".join(lines).encode("utf-8") + b"\r\n"
    tail = f"\r\n--{boundary}--\r\n".encode("utf-8")
    return head + content + tail


def _unique_default(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def run_smoke(config: SmokeConfig) -> None:
    client = SmokeClient(config.base_url, request_timeout=config.request_timeout)
    print(f"[1/8] health {config.base_url}/api/v1/health")
    health = client.get("/api/v1/health")
    _assert(health == {"status": "ok"}, f"unexpected health response: {health}")

    print("[2/8] register user")
    try:
        user = client.post_json(
            "/api/v1/auth/register",
            {"username": config.username, "email": config.email, "password": config.password},
        )
        print(f"      registered user_id={user['id']}")
    except RuntimeError as exc:
        if "HTTP 409" not in str(exc):
            raise
        print("      user already exists, continuing with login")

    print("[3/8] login")
    token_payload = client.post_json(
        "/api/v1/auth/login",
        {"username_or_email": config.username, "password": config.password},
    )
    client.token = token_payload["access_token"]
    print(f"      logged in as user_id={token_payload['user']['id']}")

    print("[4/8] create knowledge base")
    kb = client.post_json(
        "/api/v1/kbs",
        {"name": f"Smoke KB {uuid.uuid4().hex[:6]}", "description": "multitenant smoke test"},
    )
    kb_id = kb["id"]
    print(f"      kb_id={kb_id}")

    print("[5/8] upload document")
    document_text = (
        "企业知识库 Smoke 文档。\n"
        "计费规则包括调用次数、存储容量和团队席位。\n"
        "如果问题涉及计费，应引用本段内容回答。\n"
    ).encode("utf-8")
    document = client.upload_file(
        f"/api/v1/kbs/{kb_id}/documents",
        field_name="file",
        filename="smoke-billing.txt",
        content=document_text,
        content_type="text/plain",
    )
    document_id = document["id"]
    print(f"      document_id={document_id} status={document['status']}")

    print("[6/8] wait for document processing")
    document = _wait_for_document(client, document_id=document_id, timeout_seconds=config.poll_seconds)
    if document["status"] != "completed" and config.sync_fallback:
        print("      async processing not completed, invoking sync process fallback")
        process_result = client.post_json(f"/api/v1/documents/{document_id}/process", {})
        document = process_result["document"]
        print(f"      sync chunk_count={process_result['chunk_count']}")
    _assert(document["status"] == "completed", f"document did not complete: {document}")

    if config.skip_chat:
        print("[7/8] chat skipped")
    else:
        print("[7/8] ask question")
        answer = client.post_json(
            f"/api/v1/kbs/{kb_id}/chat",
            {"question": "这个系统怎么计费？"},
        )
        _assert(answer["answer"], "chat answer is empty")
        _assert(answer["references"], f"chat references are empty: {answer}")
        print(f"      session_id={answer['session_id']} references={len(answer['references'])}")

        print("[8/8] verify chat history")
        sessions = client.get("/api/v1/chat-sessions")
        _assert(any(item["id"] == answer["session_id"] for item in sessions), "session not found in history")
        messages = client.get(f"/api/v1/chat-sessions/{answer['session_id']}/messages")
        _assert(len(messages) >= 2, f"expected at least 2 chat messages, got {len(messages)}")
        print(f"      messages={len(messages)}")

    print("smoke test passed")


def _wait_for_document(client: SmokeClient, *, document_id: int, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_document = client.get(f"/api/v1/documents/{document_id}")
    while time.time() < deadline:
        last_document = client.get(f"/api/v1/documents/{document_id}")
        status = last_document["status"]
        print(f"      status={status}")
        if status in {"completed", "failed"}:
            return last_document
        time.sleep(1)
    return last_document


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def parse_args() -> SmokeConfig:
    parser = argparse.ArgumentParser(description="Run a multitenant RAG API smoke test.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--username", default=_unique_default("smoke"))
    parser.add_argument("--email", default=None)
    parser.add_argument("--password", default="password-123")
    parser.add_argument("--poll-seconds", type=int, default=30)
    parser.add_argument("--request-timeout", type=int, default=180)
    parser.add_argument("--skip-chat", action="store_true", help="Skip LLM chat call after document processing.")
    parser.add_argument(
        "--no-sync-fallback",
        action="store_true",
        help="Do not call the sync processing endpoint if async processing is still pending.",
    )
    args = parser.parse_args()
    email = args.email or f"{args.username}@example.com"
    return SmokeConfig(
        base_url=args.base_url,
        username=args.username,
        email=email,
        password=args.password,
        poll_seconds=args.poll_seconds,
        request_timeout=args.request_timeout,
        skip_chat=args.skip_chat,
        sync_fallback=not args.no_sync_fallback,
    )


if __name__ == "__main__":
    run_smoke(parse_args())
