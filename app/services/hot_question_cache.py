from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from app.config.settings import settings


@dataclass(frozen=True)
class CachedChatAnswer:
    answer: str
    references: list[dict[str, Any]]
    usage: dict[str, Any] | None = None


class InMemoryHotQuestionCache:
    def __init__(self) -> None:
        self._items: dict[str, tuple[float, CachedChatAnswer]] = {}
        self._scopes: dict[str, set[str]] = {}

    def get(self, *, key: str) -> CachedChatAnswer | None:
        item = self._items.get(key)
        if item is None:
            return None

        expires_at, value = item
        if time.monotonic() >= expires_at:
            self._items.pop(key, None)
            return None
        return value

    def set(self, *, key: str, scope_key: str, value: CachedChatAnswer, ttl_seconds: int) -> None:
        self._items[key] = (time.monotonic() + ttl_seconds, value)
        self._scopes.setdefault(scope_key, set()).add(key)

    def invalidate_scope(self, *, scope_key: str) -> None:
        keys = self._scopes.pop(scope_key, set())
        for key in keys:
            self._items.pop(key, None)


class RedisHotQuestionCache:
    def __init__(self, redis_client: Redis, *, fallback: InMemoryHotQuestionCache | None = None) -> None:
        self._redis = redis_client
        self._fallback = fallback or InMemoryHotQuestionCache()

    def get(self, *, key: str) -> CachedChatAnswer | None:
        try:
            raw_value = self._redis.get(key)
            if raw_value is None:
                return self._fallback.get(key=key)
            payload = json.loads(raw_value)
            return CachedChatAnswer(
                answer=payload["answer"],
                references=payload["references"],
                usage=payload.get("usage"),
            )
        except (RedisError, json.JSONDecodeError, KeyError, TypeError):
            return self._fallback.get(key=key)

    def set(self, *, key: str, scope_key: str, value: CachedChatAnswer, ttl_seconds: int) -> None:
        payload = json.dumps(
            {"answer": value.answer, "references": value.references, "usage": value.usage},
            ensure_ascii=False,
        )
        try:
            pipe = self._redis.pipeline()
            pipe.setex(key, ttl_seconds, payload)
            pipe.sadd(scope_key, key)
            pipe.expire(scope_key, ttl_seconds)
            pipe.execute()
        except RedisError:
            self._fallback.set(key=key, scope_key=scope_key, value=value, ttl_seconds=ttl_seconds)

    def invalidate_scope(self, *, scope_key: str) -> None:
        try:
            keys = list(self._redis.smembers(scope_key))
            if keys:
                self._redis.delete(*keys)
            self._redis.delete(scope_key)
        except RedisError:
            self._fallback.invalidate_scope(scope_key=scope_key)
        else:
            self._fallback.invalidate_scope(scope_key=scope_key)


_memory_cache = InMemoryHotQuestionCache()
_redis_cache: RedisHotQuestionCache | None = None


def build_hot_question_cache_key(
    *,
    user_id: int,
    kb_id: int,
    question: str,
    top_k: int,
) -> str:
    normalized_question = " ".join(question.strip().split()).lower()
    payload = json.dumps(
        {
            "user_id": user_id,
            "kb_id": kb_id,
            "question": normalized_question,
            "top_k": top_k,
            "chat_model": settings.chat_model,
            "embedding_model": settings.embedding_model,
            "embedding_dimension": settings.embedding_dimension,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"hot_question:answer:{digest}"


def build_hot_question_scope_key(*, user_id: int, kb_id: int) -> str:
    return f"hot_question:scope:user:{user_id}:kb:{kb_id}"


def get_hot_question_cache() -> RedisHotQuestionCache:
    global _redis_cache
    if _redis_cache is None:
        _redis_cache = RedisHotQuestionCache(Redis.from_url(settings.redis_url, decode_responses=True), fallback=_memory_cache)
    return _redis_cache
