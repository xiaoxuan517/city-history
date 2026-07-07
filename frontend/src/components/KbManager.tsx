import { FormEvent, useEffect, useState } from "react";
import { Edit3, Save, Trash2, X } from "lucide-react";

import type { KnowledgeBase } from "../types";

type KbManagerProps = {
  activeKb: KnowledgeBase | null;
  pending: boolean;
  onCreate: (payload: { name: string; description?: string }) => Promise<void>;
  onDelete: (kb: KnowledgeBase) => Promise<void>;
  onUpdate: (kb: KnowledgeBase, payload: { name: string; description?: string }) => Promise<void>;
};

function KbManager({ activeKb, pending, onCreate, onDelete, onUpdate }: KbManagerProps) {
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!activeKb || creating) return;
    setName(activeKb.name);
    setDescription(activeKb.description || "");
  }, [activeKb, creating]);

  function reset() {
    setCreating(false);
    setEditing(false);
    setError("");
    setName(activeKb?.name || "");
    setDescription(activeKb?.description || "");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const payload = { name: name.trim(), description: description.trim() || undefined };
    if (!payload.name) {
      setError("知识库名称不能为空");
      return;
    }
    try {
      if (creating) {
        await onCreate(payload);
      } else if (activeKb) {
        await onUpdate(activeKb, payload);
      }
      reset();
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存失败");
    }
  }

  async function deleteActiveKb() {
    if (!activeKb) return;
    const confirmed = window.confirm(`确认删除知识库“${activeKb.name}”？相关文档和聊天记录也会被删除。`);
    if (!confirmed) return;
    setError("");
    try {
      await onDelete(activeKb);
      reset();
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除失败");
    }
  }

  const formVisible = creating || editing || !activeKb;

  return (
    <section className="workspace-panel">
      <div className="workspace-head">
        <div>
          <p className="eyebrow">Knowledge Base</p>
          <h2>{activeKb ? activeKb.name : "创建知识库"}</h2>
        </div>
        <div className="toolbar-actions">
          {!formVisible && (
            <>
              <button className="icon-light-button" onClick={() => setEditing(true)} disabled={pending} title="编辑">
                <Edit3 size={16} />
              </button>
              <button className="icon-light-button danger" onClick={deleteActiveKb} disabled={pending} title="删除">
                <Trash2 size={16} />
              </button>
            </>
          )}
          {formVisible && activeKb && (
            <button className="icon-light-button" onClick={reset} disabled={pending} title="取消">
              <X size={16} />
            </button>
          )}
          {!formVisible && (
            <button
              className="secondary-button"
              onClick={() => {
                setCreating(true);
                setName("");
                setDescription("");
              }}
              disabled={pending}
            >
              新建
            </button>
          )}
        </div>
      </div>

      {!formVisible && activeKb && <p className="workspace-description">{activeKb.description || "暂无描述"}</p>}

      {formVisible && (
        <form className="inline-form" onSubmit={submit}>
          <label className="light-field">
            <span>名称</span>
            <input value={name} onChange={(event) => setName(event.target.value)} maxLength={128} required />
          </label>
          <label className="light-field">
            <span>描述</span>
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              maxLength={4000}
              rows={2}
            />
          </label>
          {error && <p className="form-error">{error}</p>}
          <button className="primary-button compact" disabled={pending}>
            <Save size={16} />
            保存
          </button>
        </form>
      )}
    </section>
  );
}

export default KbManager;
