import { FormEvent, useEffect, useRef, useState } from "react";
import { Bot, Send, X } from "lucide-react";

import { streamAssistantChat } from "../api";
import type { AssistantAction } from "../types";
import { AssistantActionView } from "./AssistantPage";

type FloatingAssistantMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  actions?: AssistantAction[];
  error?: boolean;
};

type FloatingAssistantProps = {
  apiToken: string;
  isAuthenticated: boolean;
  onLogin: () => void;
  onOpenKnowledgeBase: (kbId: number) => void;
};

function FloatingAssistant({
  apiToken,
  isAuthenticated,
  onLogin,
  onOpenKnowledgeBase,
}: FloatingAssistantProps) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [sessionId, setSessionId] = useState<number | undefined>(undefined);
  const [state, setState] = useState<Record<string, unknown>>({});
  const [messages, setMessages] = useState<FloatingAssistantMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content: "你好，我可以帮你检索县志、创建下载任务、查看进度，并创建知识库。",
    },
  ]);
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (open) endRef.current?.scrollIntoView({ block: "end" });
  }, [messages, open]);

  function openAssistant() {
    if (!isAuthenticated) {
      onLogin();
      return;
    }
    setOpen(true);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = input.trim();
    if (!text || pending) return;
    if (!isAuthenticated) {
      onLogin();
      return;
    }

    const assistantId = createMessageId();
    setInput("");
    setPending(true);
    setMessages((current) => [
      ...current,
      { id: createMessageId(), role: "user", content: text },
      { id: assistantId, role: "assistant", content: "正在生成..." },
    ]);

    let finalAnswer = "";
    try {
      await streamAssistantChat({
        token: apiToken,
        message: text,
        state,
        sessionId,
        onEvent: (eventData) => {
          if (eventData.eventName === "metadata") {
            setSessionId(eventData.data.session_id);
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
            setState(isRecord(response.state) ? response.state : {});
            if (response.session_id) setSessionId(response.session_id);
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
    } catch (error) {
      updateMessage(assistantId, {
        content: error instanceof Error ? error.message : "智能助手请求失败",
        error: true,
      });
    } finally {
      setPending(false);
    }
  }

  function updateMessage(id: string, patch: Partial<FloatingAssistantMessage>) {
    setMessages((current) => current.map((message) => (message.id === id ? { ...message, ...patch } : message)));
  }

  return (
    <>
      <button
        type="button"
        className="floating-assistant-button"
        title="智能机器人"
        aria-label="智能机器人"
        onClick={openAssistant}
      >
        <Bot size={26} />
        <span>智能机器人</span>
      </button>

      {open && (
        <aside className="floating-assistant-panel" aria-label="智能机器人聊天框">
          <header className="floating-assistant-head">
            <div>
              <small>智能机器人</small>
              <h2>县志助手</h2>
            </div>
            <button type="button" title="关闭" onClick={() => setOpen(false)}>
              <X size={18} />
            </button>
          </header>

          <div className="floating-assistant-chat">
            {messages.map((message) => (
              <article className={`floating-assistant-message ${message.role} ${message.error ? "error" : ""}`} key={message.id}>
                <div className="floating-assistant-avatar">{message.role === "assistant" ? <Bot size={16} /> : "你"}</div>
                <div className="floating-assistant-bubble">
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
            <div ref={endRef} />
          </div>

          <form className="floating-assistant-composer" onSubmit={submit}>
            <input
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="问我检索、下载或创建知识库"
              disabled={pending}
            />
            <button type="submit" disabled={pending || !input.trim()}>
              <Send size={17} />
            </button>
          </form>
        </aside>
      )}
    </>
  );
}

function createMessageId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `message-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export default FloatingAssistant;
