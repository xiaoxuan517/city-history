import { FormEvent, useEffect, useState } from "react";
import { Bot, BookOpen, Download, MessageSquare, Plus, Send, Trash2 } from "lucide-react";

import { deleteChatSession, listChatMessages, listChatSessions, streamAssistantChat } from "../api";
import type { AssistantAction, ChatSession, StoredChatMessage } from "../types";
import SiteNav from "./SiteNav";

type AssistantMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  actions?: AssistantAction[];
  error?: boolean;
};

type AssistantPageProps = {
  apiStatus: string;
  apiToken: string;
  isAuthenticated: boolean;
  username?: string;
  onHome: () => void;
  onGazetteers: () => void;
  onKnowledgeBase: () => void;
  onHistoryAlbum: () => void;
  onFavorites: () => void;
  onLogin: () => void;
  onLogout: () => void;
  onOpenKnowledgeBase: (kbId: number) => void;
};

function AssistantPage({
  apiStatus,
  apiToken,
  isAuthenticated,
  username,
  onHome,
  onGazetteers,
  onKnowledgeBase,
  onHistoryAlbum,
  onFavorites,
  onLogin,
  onLogout,
  onOpenKnowledgeBase,
}: AssistantPageProps) {
  const [messages, setMessages] = useState<AssistantMessage[]>([
    welcomeAssistantMessage(),
  ]);
  const [state, setState] = useState<Record<string, unknown>>({});
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<number | undefined>(undefined);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [sessionPending, setSessionPending] = useState(false);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isAuthenticated) return;
    void refreshSessions();
  }, [apiToken, isAuthenticated]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = input.trim();
    if (!text || pending) return;
    if (!isAuthenticated) {
      onLogin();
      return;
    }

    setInput("");
    setPending(true);
    setError("");
    const assistantId = createMessageId();
    setMessages((current) => [
      ...current,
      { id: createMessageId(), role: "user", content: text },
      { id: assistantId, role: "assistant", content: "正在生成..." },
    ]);
    let finalSessionId = activeSessionId;
    let finalAnswer = "";
    try {
      await streamAssistantChat({
        token: apiToken,
        message: text,
        state,
        sessionId: activeSessionId,
        onEvent: (eventData) => {
          if (eventData.eventName === "metadata") {
            finalSessionId = eventData.data.session_id;
            setActiveSessionId(eventData.data.session_id);
            return;
          }
          if (eventData.eventName === "answer_delta") {
            const nextAnswer = eventData.data.answer || eventData.data.content || "";
            finalAnswer = nextAnswer;
            updateMessage(assistantId, { content: nextAnswer || "正在生成..." });
            return;
          }
          if (eventData.eventName === "complete") {
            const response = eventData.data;
            finalAnswer = typeof response.answer === "string" ? response.answer : finalAnswer;
            finalSessionId = response.session_id ?? finalSessionId;
            setState(isRecord(response.state) ? response.state : {});
            if (response.session_id) setActiveSessionId(response.session_id);
            updateMessage(assistantId, {
              content: finalAnswer || "智能助手已返回结果。",
              actions: Array.isArray(response.actions) ? response.actions : [],
            });
            return;
          }
          if (eventData.eventName === "error") {
            throw new Error(eventData.data.message || "智能助手请求失败");
          }
        },
      });
      if (!finalAnswer) updateMessage(assistantId, { content: "没有收到回答。" });
      await refreshSessions(finalSessionId);
    } catch (error) {
      updateMessage(assistantId, {
        content: error instanceof Error ? error.message : "智能助手请求失败",
        error: true,
      });
    } finally {
      setPending(false);
    }
  }

  async function refreshSessions(preferredSessionId = activeSessionId) {
    if (!apiToken) return;
    setSessionsLoading(true);
    try {
      const allSessions = await listChatSessions(apiToken);
      const assistantSessions = allSessions.filter((session) => session.kb_id === null);
      setSessions(assistantSessions);
      if (preferredSessionId && assistantSessions.some((session) => session.id === preferredSessionId)) {
        setActiveSessionId(preferredSessionId);
      }
    } catch (error) {
      setError(error instanceof Error ? error.message : "加载会话失败");
    } finally {
      setSessionsLoading(false);
    }
  }

  async function selectSession(session: ChatSession) {
    if (!apiToken || pending) return;
    setSessionPending(true);
    setError("");
    try {
      const storedMessages = await listChatMessages(apiToken, session.id);
      setActiveSessionId(session.id);
      setState({});
      setMessages(storedMessages.length ? storedMessages.map(toAssistantMessage) : [welcomeAssistantMessage()]);
    } catch (error) {
      setError(error instanceof Error ? error.message : "加载会话消息失败");
    } finally {
      setSessionPending(false);
    }
  }

  async function removeSession(session: ChatSession) {
    if (!apiToken || pending) return;
    const confirmed = window.confirm(`确认删除会话“${session.title || `会话 ${session.id}`}”？`);
    if (!confirmed) return;
    setSessionPending(true);
    setError("");
    try {
      await deleteChatSession(apiToken, session.id);
      setSessions((current) => current.filter((item) => item.id !== session.id));
      if (activeSessionId === session.id) startNewSession();
    } catch (error) {
      setError(error instanceof Error ? error.message : "删除会话失败");
    } finally {
      setSessionPending(false);
    }
  }

  function startNewSession() {
    setActiveSessionId(undefined);
    setState({});
    setInput("");
    setMessages([welcomeAssistantMessage()]);
  }

  function updateMessage(id: string, patch: Partial<AssistantMessage>) {
    setMessages((current) => current.map((message) => (message.id === id ? { ...message, ...patch } : message)));
  }

  return (
    <main className="heritage-home assistant-page">
      <SiteNav
        active="assistant"
        isAuthenticated={isAuthenticated}
        username={username}
        onHome={onHome}
        onGazetteers={onGazetteers}
        onKnowledgeBase={onKnowledgeBase}
        onAssistant={() => undefined}
        onHistoryAlbum={onHistoryAlbum}
        onFavorites={onFavorites}
        onLogin={onLogin}
        onLogout={onLogout}
      />

      <section className="assistant-page-shell">
        <header className="assistant-hero">
          <div>
            <p className="home-eyebrow">智能助手</p>
            <h1>县志智能助手</h1>
            <p>用对话完成县志检索、下载任务、下载进度查询和知识库创建。</p>
          </div>
          <span className={apiStatus === "可用" ? "tone-ok" : "tone-bad"}>服务{apiStatus}</span>
        </header>

        <section className="assistant-layout">
          <aside className="assistant-session-panel" aria-label="智能助手会话">
            <div className="assistant-session-head">
              <h2>会话记录</h2>
              <button type="button" title="新会话" onClick={startNewSession} disabled={pending || sessionPending}>
                <Plus size={17} />
              </button>
            </div>
            <div className="assistant-session-list">
              {sessionsLoading && <p className="assistant-session-loading">正在加载记录...</p>}
              {!sessionsLoading && sessions.map((session) => (
                <div className={`assistant-session-item ${activeSessionId === session.id ? "active" : ""}`} key={session.id}>
                  <button
                    className="assistant-session-select"
                    type="button"
                    onClick={() => void selectSession(session)}
                    disabled={pending || sessionPending}
                  >
                    <MessageSquare size={16} />
                    <span>{session.title || `会话 ${session.id}`}</span>
                    <small>{formatDate(session.updated_at)}</small>
                  </button>
                  <button
                    className="assistant-session-delete"
                    type="button"
                    title="删除会话"
                    disabled={pending || sessionPending}
                    onClick={() => void removeSession(session)}
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              ))}
              {!sessionsLoading && !sessions.length && <p>还没有历史会话。</p>}
            </div>
          </aside>

          <section className="assistant-shell">
            {error && <p className="assistant-error">{error}</p>}

            <div className="assistant-chat">
              {messages.map((message) => (
                <article className={`assistant-message ${message.role} ${message.error ? "error" : ""}`} key={message.id}>
                  <div className="assistant-avatar">{message.role === "assistant" ? <Bot size={18} /> : "你"}</div>
                  <div className="assistant-bubble">
                    <p>{message.content}</p>
                    {message.actions?.map((action, index) => (
                      <AssistantActionView
                        action={action}
                        key={`${action.type}-${index}`}
                        onOpenKnowledgeBase={onOpenKnowledgeBase}
                      />
                    ))}
                  </div>
                </article>
              ))}
            </div>

            <form className="assistant-composer" onSubmit={submit}>
              <input
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder="例如：帮我找江宁县志；下载第 1 本；查看下载进度；创建知识库"
                disabled={pending || sessionPending}
              />
              <button type="submit" disabled={pending || sessionPending || !input.trim()}>
                <Send size={18} />
                {pending ? "处理中" : "发送"}
              </button>
            </form>
          </section>
        </section>
      </section>
    </main>
  );
}

export function AssistantActionView({
  action,
  onOpenKnowledgeBase,
}: {
  action: AssistantAction;
  onOpenKnowledgeBase: (kbId: number) => void;
}) {
  const payload = isRecord(action.payload) ? action.payload : {};

  if (action.type === "gazetteer_candidates") {
    const items = Array.isArray(payload.items) ? payload.items : [];
    return (
      <div className="assistant-card-list">
        {items.map((raw, index) => {
          const item = raw as Record<string, unknown>;
          return (
            <div className="assistant-action-card" key={String(item.id || index)}>
              <strong>{index + 1}. {String(item.name || "未命名县志")}</strong>
              <span>{String(item.full_path || "")}</span>
              <small>{item.is_downloaded ? "已下载" : "未下载"}</small>
            </div>
          );
        })}
      </div>
    );
  }

  if (action.type === "download_task") {
    const task = isRecord(payload.task) ? payload.task : {};
    return (
      <div className="assistant-action-card compact">
        <Download size={17} />
        <div>
          <strong>下载任务</strong>
          <span>{String(task.status || "")}</span>
          <small>进度 {Number(task.progress || 0)}%</small>
        </div>
      </div>
    );
  }

  if (action.type === "knowledge_base") {
    const id = Number(payload.id);
    return (
      <button className="assistant-open-kb" type="button" onClick={() => onOpenKnowledgeBase(id)} disabled={!id}>
        <BookOpen size={17} />
        打开知识库：{String(payload.name || id)}
      </button>
    );
  }

  return null;
}

function welcomeAssistantMessage(): AssistantMessage {
  return {
    id: "welcome",
    role: "assistant",
    content: "我可以帮你检索县志、创建下载任务、查看进度，并把已下载县志创建为知识库。",
  };
}

function toAssistantMessage(message: StoredChatMessage): AssistantMessage {
  return {
    id: `stored-${message.id}`,
    role: message.role === "assistant" ? "assistant" : "user",
    content: message.content,
    actions: extractStoredAssistantActions(message),
  };
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString("zh-CN");
}

function createMessageId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `message-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function extractStoredAssistantActions(message: StoredChatMessage): AssistantAction[] {
  if (message.role !== "assistant") return [];
  return message.references
    .map((reference) => {
      const item = isRecord(reference) ? (reference as Record<string, unknown>) : {};
      return isRecord(item.action) ? item.action : null;
    })
    .filter((action): action is AssistantAction => isRecord(action) && typeof action.type === "string");
}

export default AssistantPage;
