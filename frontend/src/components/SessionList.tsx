import { MessageSquare, Plus, Trash2 } from "lucide-react";

import type { ChatSession } from "../types";

type SessionListProps = {
  activeSessionId?: number;
  disabled?: boolean;
  sessions: ChatSession[];
  onDeleteSession: (session: ChatSession) => void;
  onNewSession: () => void;
  onSelectSession: (session: ChatSession) => void;
};

function SessionList({
  activeSessionId,
  disabled,
  sessions,
  onDeleteSession,
  onNewSession,
  onSelectSession,
}: SessionListProps) {
  return (
    <div className="session-list">
      <button className="session-new-button" disabled={disabled} onClick={onNewSession} type="button">
        <Plus size={16} />
        新会话
      </button>
      {sessions.length ? (
        <div className="session-items">
          {sessions.map((session) => (
            <div className={`session-item ${session.id === activeSessionId ? "active" : ""}`} key={session.id}>
              <button
                className="session-open-button"
                disabled={disabled}
                onClick={() => onSelectSession(session)}
                title={session.title || `会话 ${session.id}`}
                type="button"
              >
                <MessageSquare size={15} />
                <span>{session.title || `会话 ${session.id}`}</span>
              </button>
              <button
                className="session-delete-button"
                disabled={disabled}
                onClick={() => onDeleteSession(session)}
                title="删除会话"
                type="button"
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      ) : (
        <p className="panel-note">当前知识库还没有历史会话。</p>
      )}
    </div>
  );
}

export default SessionList;
