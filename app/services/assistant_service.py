from __future__ import annotations

import json
import mimetypes
import re
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.create_agent import build_model
from app.db.models.chat import ChatMessage, ChatRole, ChatRun, ChatRunEvent, ChatRunStatus, ChatSession
from app.db.models.gazetteer_file import GazetteerFile
from app.schemas.alist import AListOfflineDownloadRequest, AListTask, AListTaskListRequest
from app.schemas.assistant import AssistantAction, AssistantChatResponse
from app.schemas.knowledge_base import KnowledgeBaseCreate
from app.services.alist_service import AListService
from app.services.document_service import DocumentService
from app.services.gazetteer_file_service import GazetteerFileService, source_path_for_display_path
from app.services.kb_service import KnowledgeBaseService
from app.workers.tasks import get_document_task_dispatcher


class AssistantService:
    def __init__(
        self,
        *,
        gazetteer_file_service: GazetteerFileService | None = None,
        alist_service: AListService | None = None,
        kb_service: KnowledgeBaseService | None = None,
        document_service: DocumentService | None = None,
    ) -> None:
        self._gazetteer_files = gazetteer_file_service or GazetteerFileService()
        self._alist = alist_service or AListService()
        self._kb = kb_service or KnowledgeBaseService()
        self._documents = document_service or DocumentService()

    def chat(
        self,
        session: Session,
        *,
        user_id: int,
        message: str,
        state: dict[str, Any],
        session_id: int | None = None,
    ) -> AssistantChatResponse:
        text = message.strip()
        next_state = dict(state or {})
        actions: list[AssistantAction] = []
        chat_session = _get_or_create_assistant_session(session, user_id=user_id, session_id=session_id, question=text)
        if not next_state:
            next_state = _latest_assistant_state(session, chat_session_id=chat_session.id)
        next_state.setdefault("assistant_session_id", chat_session.id)
        session.add(ChatMessage(session_id=chat_session.id, role=ChatRole.USER, content=text, references=[]))
        session.commit()
        chat_run = _create_assistant_run(session, user_id=user_id, chat_session_id=chat_session.id, question=text)
        event_sequence = 0

        def record_tool_result(tool_name: str, response: AssistantChatResponse) -> None:
            nonlocal event_sequence
            event_sequence += 1
            _record_assistant_run_event(
                session,
                chat_run=chat_run,
                event_type="tool_result",
                sequence=event_sequence,
                payload={
                    "tool_name": tool_name,
                    "answer": response.answer,
                    "actions": [action.model_dump() for action in response.actions],
                    "state": response.state,
                },
            )

        @tool
        def search_gazetteer_files(query: str) -> str:
            """Search gazetteer files by place name, old place name, title, or path."""
            response = self._search(session, text=query, state=next_state)
            actions.extend(response.actions)
            record_tool_result("search_gazetteer_files", response)
            return _tool_payload(answer=response.answer, state=response.state, actions=response.actions)

        @tool
        def download_gazetteer(index: int = 1) -> str:
            """Create a download task for one gazetteer from the latest search result list. Index starts from 1."""
            response = self._download_selected(session, text=f"下载第 {index} 本", state=next_state)
            actions.extend(response.actions)
            record_tool_result("download_gazetteer", response)
            return _tool_payload(answer=response.answer, state=response.state, actions=response.actions)

        @tool
        def get_download_status() -> str:
            """Get current download task status and progress for the selected gazetteer."""
            response = self._download_status(next_state)
            actions.extend(response.actions)
            record_tool_result("get_download_status", response)
            return _tool_payload(answer=response.answer, state=response.state, actions=response.actions)

        @tool
        def create_or_open_knowledge_base() -> str:
            """Create a knowledge base from the selected downloaded gazetteer, or open existing same-name knowledge base."""
            response = self._create_or_open_kb(session, user_id=user_id, state=next_state)
            actions.extend(response.actions)
            record_tool_result("create_or_open_knowledge_base", response)
            return _tool_payload(answer=response.answer, state=response.state, actions=response.actions)

        try:
            agent = create_agent(
                model=build_model(),
                tools=[
                    search_gazetteer_files,
                    download_gazetteer,
                    get_download_status,
                    create_or_open_knowledge_base,
                ],
                system_prompt=_assistant_system_prompt(next_state),
            )
            result = agent.invoke({"messages": [{"role": "user", "content": text}]})
            answer = _final_answer(result.get("messages", [])) or "我已处理完成。"
            session.add(ChatMessage(session_id=chat_session.id, role=ChatRole.ASSISTANT, content=answer, references=[]))
            chat_run.status = ChatRunStatus.COMPLETED
            chat_run.answer = answer
            chat_run.references = []
            chat_run.usage = _zero_usage()
            chat_run.token_cost = {}
            chat_run.cache_hit = False
            chat_run.error_message = None
            event_sequence += 1
            _record_assistant_run_event(
                session,
                chat_run=chat_run,
                event_type="complete",
                sequence=event_sequence,
                payload={
                    "answer_preview": answer[:500],
                    "action_count": len(actions),
                    "state": next_state,
                },
            )
            session.commit()
            return AssistantChatResponse(
                answer=answer,
                actions=actions,
                state=next_state,
                session_id=chat_session.id,
                run_id=chat_run.id,
            )
        except Exception as exc:
            chat_run.status = ChatRunStatus.FAILED
            chat_run.error_message = str(exc)
            event_sequence += 1
            _record_assistant_run_event(
                session,
                chat_run=chat_run,
                event_type="error",
                sequence=event_sequence,
                payload={"message": str(exc), "state": next_state},
            )
            session.commit()
            raise

    def _search(self, session: Session, *, text: str, state: dict[str, Any]) -> AssistantChatResponse:
        query = _search_query(text)
        rows, total = self._gazetteer_files.list_files(session, q=query, page=1, per_page=10)
        candidates = [_gazetteer_payload(row, self._alist) for row in rows]
        state["last_candidates"] = candidates
        actions = [AssistantAction(type="gazetteer_candidates", payload={"items": candidates, "total": total})]
        if not candidates:
            return AssistantChatResponse(answer=f"没有找到与“{query}”相关的县志。", actions=actions, state=state)
        return AssistantChatResponse(
            answer=f"找到 {total} 条与“{query}”相关的县志，下面列出前 {len(candidates)} 条。你可以说“下载第 1 本”。",
            actions=actions,
            state=state,
        )

    def _download_selected(self, session: Session, *, text: str, state: dict[str, Any]) -> AssistantChatResponse:
        candidate = _selected_candidate(text, state)
        if candidate is None:
            return self._search(session, text=text.replace("下载", ""), state=state)

        row = session.get(GazetteerFile, int(candidate["id"]))
        if row is None:
            return AssistantChatResponse(answer="没有找到这个县志条目，请重新检索。", state=state)

        source_path = source_path_for_display_path(row.full_path)
        response = self._alist.add_offline_download(
            AListOfflineDownloadRequest(
                source_path=source_path,
                list_path=_parent_path(source_path),
                name=row.name,
            )
        )
        task = response.data.tasks[0] if response.data.tasks else None
        if task is None:
            return AssistantChatResponse(answer="下载任务创建失败：AList 没有返回任务。", state=state)

        state["selected_file"] = _gazetteer_payload(row, self._alist)
        state["download_task_id"] = task.id
        action = AssistantAction(type="download_task", payload={"task": task.model_dump(), "file": state["selected_file"]})
        if _task_done(task):
            answer = "该县志本地已下载完成。你可以说“创建知识库”。"
        else:
            answer = "已创建下载任务，我会记录这个任务。你可以稍后说“查看下载进度”。"
        return AssistantChatResponse(answer=answer, actions=[action], state=state)

    def _download_status(self, state: dict[str, Any]) -> AssistantChatResponse:
        task_id = str(state.get("download_task_id") or "")
        if not task_id:
            return AssistantChatResponse(answer="当前没有记录中的下载任务。", state=state)
        response = self._alist.list_offline_download_tasks(AListTaskListRequest(task_ids=[task_id]))
        task = response.data.tasks[0] if response.data.tasks else None
        if task is None:
            return AssistantChatResponse(answer="没有查询到这个下载任务，可能任务已丢失。", state=state)
        action = AssistantAction(type="download_task", payload={"task": task.model_dump(), "file": state.get("selected_file")})
        answer = "下载已完成，可以创建知识库。" if _task_done(task) else f"下载中，当前进度 {task.progress or 0}%。"
        return AssistantChatResponse(answer=answer, actions=[action], state=state)

    def _create_or_open_kb(self, session: Session, *, user_id: int, state: dict[str, Any]) -> AssistantChatResponse:
        selected_file = state.get("selected_file")
        if not isinstance(selected_file, dict):
            return AssistantChatResponse(answer="请先选择并下载一本县志，再创建知识库。", state=state)

        filename = str(selected_file.get("name") or "")
        kb_name = _knowledge_base_name(filename)
        existing = self._kb.get_by_name_for_user(session, user_id=user_id, name=kb_name)
        if existing is not None:
            state["knowledge_base_id"] = existing.id
            action = AssistantAction(type="knowledge_base", payload={"id": existing.id, "name": existing.name, "created": False})
            return AssistantChatResponse(answer=f"已存在同名知识库“{existing.name}”，我已为你打开。", actions=[action], state=state)

        task_id = str(state.get("download_task_id") or "")
        if not task_id:
            task = self._alist.get_existing_local_download_task(filename)
            task_id = task.id if task else ""
        if not task_id:
            return AssistantChatResponse(answer="这本县志还没有下载完成，请先创建下载任务并等待完成。", state=state)

        file_path = self._alist.get_local_download_path(task_id)
        kb = self._kb.create(
            session,
            user_id=user_id,
            payload=KnowledgeBaseCreate(name=kb_name, description=f"由县志文件 {filename} 创建"),
        )
        document = self._documents.create_from_local_file(
            session,
            user_id=user_id,
            kb_id=kb.id,
            source_path=file_path,
            content_type=mimetypes.guess_type(file_path.name)[0],
        )
        try:
            get_document_task_dispatcher()(document.id)
        except Exception:
            pass

        state["knowledge_base_id"] = kb.id
        action = AssistantAction(
            type="knowledge_base",
            payload={"id": kb.id, "name": kb.name, "document_id": document.id, "created": True},
        )
        return AssistantChatResponse(answer=f"已创建知识库“{kb.name}”，并加入文档“{document.filename}”。", actions=[action], state=state)

    @staticmethod
    def _is_download_intent(text: str) -> bool:
        return "下载" in text

    @staticmethod
    def _is_status_intent(text: str) -> bool:
        return any(word in text for word in ["进度", "状态", "下载好了", "完成了吗"])

    @staticmethod
    def _is_create_kb_intent(text: str) -> bool:
        return any(word in text for word in ["创建知识库", "加入知识库", "建立知识库", "打开知识库"])


def _gazetteer_payload(row: GazetteerFile, alist_service: AListService) -> dict[str, Any]:
    task = alist_service.get_existing_local_download_task(row.name)
    return {
        "id": row.id,
        "name": row.name,
        "full_path": row.full_path,
        "source_path": source_path_for_display_path(row.full_path),
        "size": row.size,
        "modified": row.modified,
        "is_downloaded": task is not None,
        "local_download_task_id": task.id if task else None,
    }


def _selected_candidate(text: str, state: dict[str, Any]) -> dict[str, Any] | None:
    candidates = state.get("last_candidates")
    if not isinstance(candidates, list) or not candidates:
        return None
    index = 0
    match = re.search(r"第\s*(\d+)\s*[本个条]?", text)
    if match:
        index = max(0, int(match.group(1)) - 1)
    if index >= len(candidates):
        return None
    candidate = candidates[index]
    return candidate if isinstance(candidate, dict) else None


def _search_query(text: str) -> str:
    cleaned = text.strip()
    for word in ["帮我", "请", "查找", "搜索", "检索", "找", "相关", "县志", "古籍"]:
        cleaned = cleaned.replace(word, "")
    return cleaned.strip(" ，。,.") or text.strip()


def _parent_path(path: str) -> str:
    normalized = path.replace("/", "/").rstrip("/")
    return normalized[: normalized.rfind("/")] or "/"


def _knowledge_base_name(filename: str) -> str:
    name = re.sub(r"\.[^.]+$", "", filename).strip() or filename.strip() or "县志知识库"
    return name[:128]


def _task_done(task: AListTask) -> bool:
    return not task.error and (task.progress >= 100 or task.state == 2)


def _assistant_system_prompt(state: dict[str, Any]) -> str:
    return (
        "你是“方志云藏”的县志智能助手。你可以和用户自然对话，也可以在需要时调用工具。\n"
        "你的职责：帮助用户检索县志、创建下载任务、查看下载进度、创建或打开知识库。\n"
        "工具使用规则：\n"
        "1. 用户只是问候、问你是谁、咨询能力时，不要调用工具，直接回答。\n"
        "2. 用户要求查找、搜索、检索某地或某书县志时，调用 search_gazetteer_files。\n"
        "3. 用户要求下载某条候选结果时，调用 download_gazetteer。候选序号从 1 开始。\n"
        "4. 用户询问下载进度、是否完成时，调用 get_download_status。\n"
        "5. 用户要求创建、加入或打开知识库时，调用 create_or_open_knowledge_base。\n"
        "6. 不要编造县志文件、下载任务或知识库 id；这些信息必须来自工具结果。\n"
        "7. 回答使用中文，简洁说明下一步可做什么。\n"
        f"当前会话状态 JSON：{json.dumps(state, ensure_ascii=False, default=str)}"
    )


def _tool_payload(
    *,
    answer: str,
    state: dict[str, Any],
    actions: list[AssistantAction],
) -> str:
    return json.dumps(
        {
            "answer": answer,
            "state": state,
            "actions": [action.model_dump() for action in actions],
        },
        ensure_ascii=False,
        default=str,
    )


def _final_answer(messages: list[Any]) -> str:
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            content = message.content
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                return "\n".join(str(item.get("text", item)) if isinstance(item, dict) else str(item) for item in content)
            return str(content).strip()
    return ""


def _get_or_create_assistant_session(
    session: Session,
    *,
    user_id: int,
    session_id: int | None,
    question: str,
) -> ChatSession:
    if session_id is not None:
        chat_session = session.get(ChatSession, session_id)
        if chat_session is not None and chat_session.user_id == user_id and chat_session.kb_id is None:
            return chat_session
    title = question.strip()[:60] or "智能助手会话"
    chat_session = ChatSession(user_id=user_id, kb_id=None, title=title)
    session.add(chat_session)
    session.commit()
    session.refresh(chat_session)
    return chat_session


def _create_assistant_run(session: Session, *, user_id: int, chat_session_id: int, question: str) -> ChatRun:
    chat_run = ChatRun(
        session_id=chat_session_id,
        user_id=user_id,
        kb_id=None,
        prompt_version_id=None,
        status=ChatRunStatus.RUNNING,
        question=question,
        references=[],
        usage={},
        token_cost={},
        cache_hit=False,
    )
    session.add(chat_run)
    session.commit()
    session.refresh(chat_run)
    return chat_run


def _record_assistant_run_event(
    session: Session,
    *,
    chat_run: ChatRun,
    event_type: str,
    sequence: int,
    payload: dict[str, Any],
) -> None:
    session.add(
        ChatRunEvent(
            run_id=chat_run.id,
            user_id=chat_run.user_id,
            kb_id=None,
            event_type=event_type,
            sequence=sequence,
            payload=payload,
        )
    )


def _latest_assistant_state(session: Session, *, chat_session_id: int) -> dict[str, Any]:
    statement = (
        select(ChatRunEvent)
        .join(ChatRun, ChatRunEvent.run_id == ChatRun.id)
        .where(ChatRun.session_id == chat_session_id, ChatRunEvent.event_type == "complete")
        .order_by(ChatRunEvent.created_at.desc(), ChatRunEvent.id.desc())
        .limit(1)
    )
    event = session.scalar(statement)
    if event is None:
        return {}
    state = event.payload.get("state") if isinstance(event.payload, dict) else None
    return dict(state) if isinstance(state, dict) else {}


def _zero_usage() -> dict[str, Any]:
    return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cached": False}


def get_assistant_service() -> AssistantService:
    return AssistantService()
