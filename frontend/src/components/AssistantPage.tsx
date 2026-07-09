import { FormEvent, useState } from "react";
import { Bot, BookOpen, Download, Landmark, Send } from "lucide-react";

import { chatWithAssistant } from "../api";
import type { AssistantAction } from "../types";
import UserMenu from "./UserMenu";

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
  onLogin,
  onLogout,
  onOpenKnowledgeBase,
}: AssistantPageProps) {
  const [messages, setMessages] = useState<AssistantMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content: "我可以帮你检索县志、创建下载任务、查看进度，并把已下载县志创建为知识库。",
    },
  ]);
  const [state, setState] = useState<Record<string, unknown>>({});
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);

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
    setMessages((current) => [...current, { id: crypto.randomUUID(), role: "user", content: text }]);
    try {
      const response = await chatWithAssistant(apiToken, { message: text, state });
      setState(response.state);
      setMessages((current) => [
        ...current,
        { id: crypto.randomUUID(), role: "assistant", content: response.answer, actions: response.actions },
      ]);
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: error instanceof Error ? error.message : "智能助手请求失败",
          error: true,
        },
      ]);
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="heritage-home assistant-page">
      <nav className="site-nav" aria-label="主导航">
        <button className="nav-brand" type="button" onClick={onHome}>
          <Landmark size={24} />
          <span>方志云藏</span>
        </button>
        <div className="nav-links">
          <button type="button" onClick={onGazetteers}>县志</button>
          <button type="button" onClick={onKnowledgeBase}>知识库</button>
          <button type="button" className="active">智能助手</button>
          <button type="button" onClick={onHistoryAlbum}>历史图册</button>
        </div>
        <UserMenu isAuthenticated={isAuthenticated} username={username} onLogin={onLogin} onLogout={onLogout} />
      </nav>

      <section className="assistant-shell">
        <header className="assistant-hero">
          <div>
            <p className="home-eyebrow">Project Agent</p>
            <h1>县志智能助手</h1>
            <p>用对话完成县志检索、下载任务、下载进度查询和知识库创建。</p>
          </div>
          <span className={apiStatus === "可用" ? "tone-ok" : "tone-bad"}>API {apiStatus}</span>
        </header>

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
            disabled={pending}
          />
          <button type="submit" disabled={pending || !input.trim()}>
            <Send size={18} />
            {pending ? "处理中" : "发送"}
          </button>
        </form>
      </section>
    </main>
  );
}

function AssistantActionView({
  action,
  onOpenKnowledgeBase,
}: {
  action: AssistantAction;
  onOpenKnowledgeBase: (kbId: number) => void;
}) {
  if (action.type === "gazetteer_candidates") {
    const items = Array.isArray(action.payload.items) ? action.payload.items : [];
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
    const task = (action.payload.task || {}) as Record<string, unknown>;
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
    const id = Number(action.payload.id);
    return (
      <button className="assistant-open-kb" type="button" onClick={() => onOpenKnowledgeBase(id)} disabled={!id}>
        <BookOpen size={17} />
        打开知识库：{String(action.payload.name || id)}
      </button>
    );
  }

  return null;
}

export default AssistantPage;
