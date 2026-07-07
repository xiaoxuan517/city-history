import { ChevronDown, LogOut, PanelLeft, Plus } from "lucide-react";
import { useMemo } from "react";

import type { ChatSession, KnowledgeBase, PublicConfig, RetrievalProfile, User } from "../types";
import RetrievalSettings from "./RetrievalSettings";
import SessionList from "./SessionList";

type SidebarProps = {
  activeKbId: number | null;
  apiStatus: string;
  config: PublicConfig | null;
  defaultRetrievalProfile: RetrievalProfile | null;
  knowledgeBases: KnowledgeBase[];
  chatSessions: ChatSession[];
  pending: boolean;
  retrievalProfile: RetrievalProfile | null;
  threadId: string;
  user: User;
  workspaceError: string;
  workspacePending: boolean;
  onCreateKb: () => void;
  onKbChange: (kbId: number) => void;
  onLogout: () => void;
  onRetrievalProfileChange: (profile: RetrievalProfile) => void;
  onResetThread: () => void;
  onSessionDelete: (session: ChatSession) => void;
  onSessionSelect: (session: ChatSession) => void;
};

function Sidebar({
  activeKbId,
  apiStatus,
  config,
  defaultRetrievalProfile,
  knowledgeBases,
  chatSessions,
  pending,
  retrievalProfile,
  threadId,
  user,
  workspaceError,
  workspacePending,
  onCreateKb,
  onKbChange,
  onLogout,
  onRetrievalProfileChange,
  onResetThread,
  onSessionDelete,
  onSessionSelect,
}: SidebarProps) {
  const configRows = useMemo(() => {
    if (!config) return [["模型", "-"]];
    return [
      ["模型", config.chat_model],
      ["Embedding", config.embedding_model],
      ["检索", config.retrieval_search_type],
      ["Top K", String(config.top_k)],
      ["Fetch K", String(config.retrieval_fetch_k)],
      ["Reranker", config.reranker_enabled ? "on" : "off"],
      ["Context", `${config.retrieval_max_context_chars} chars`],
    ];
  }, [config]);

  return (
    <aside className="sidebar" aria-label="控制台信息">
      <section className="panel">
        <div className="panel-head">
          <h2>{user.username}</h2>
          <button className="icon-button" onClick={onLogout} title="退出登录" type="button">
            <LogOut size={18} />
          </button>
        </div>
        <dl className="meta-list">
          <MetaRow label="邮箱" value={user.email} />
          <MetaRow label="状态" value={apiStatus} tone={apiStatus === "可用" ? "ok" : "bad"} />
        </dl>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>知识库</h2>
          <button className="icon-button" onClick={onCreateKb} disabled={workspacePending} title="创建默认知识库">
            <Plus size={18} />
          </button>
        </div>
        {knowledgeBases.length ? (
          <label className="field">
            <span>当前知识库</span>
            <select
              value={activeKbId || ""}
              onChange={(event) => onKbChange(Number(event.target.value))}
              disabled={pending || workspacePending}
            >
              {knowledgeBases.map((kb) => (
                <option key={kb.id} value={kb.id}>
                  {kb.name}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <p className="panel-note">还没有知识库，先创建一个默认知识库。</p>
        )}
        {workspaceError && <p className="panel-error">{workspaceError}</p>}
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>会话</h2>
        </div>
        <SessionList
          activeSessionId={threadId && threadId !== "-" ? Number(threadId) : undefined}
          disabled={pending || workspacePending}
          onDeleteSession={onSessionDelete}
          sessions={chatSessions}
          onNewSession={onResetThread}
          onSelectSession={onSessionSelect}
        />
      </section>

      <details className="panel collapsible-panel">
        <summary className="panel-head">
          <h2>检索配置</h2>
          <span className="collapse-icons">
            <PanelLeft size={16} aria-hidden="true" />
            <ChevronDown size={16} aria-hidden="true" />
          </span>
        </summary>
        <dl className="meta-list">
          {configRows.map(([label, value]) => (
            <MetaRow key={label} label={label} value={value} />
          ))}
        </dl>
      </details>

      <RetrievalSettings
        defaultProfile={defaultRetrievalProfile}
        disabled={pending}
        profile={retrievalProfile}
        onChange={onRetrievalProfileChange}
      />
    </aside>
  );
}

function MetaRow({ label, value, tone }: { label: string; value: string; tone?: "ok" | "bad" }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd className={tone ? `tone-${tone}` : undefined}>{value}</dd>
    </div>
  );
}

export default Sidebar;
