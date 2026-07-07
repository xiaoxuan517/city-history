import { ChangeEvent, useRef, useState } from "react";
import { FileUp, Play, RefreshCw, Trash2 } from "lucide-react";

import type { KnowledgeDocument } from "../types";

type DocumentPanelProps = {
  documents: KnowledgeDocument[];
  pending: boolean;
  onDelete: (document: KnowledgeDocument) => Promise<void>;
  onProcess: (document: KnowledgeDocument) => Promise<void>;
  onRefresh: () => Promise<void>;
  onUpload: (file: File) => Promise<void>;
};

const statusLabels: Record<KnowledgeDocument["status"], string> = {
  pending: "待处理",
  processing: "处理中",
  completed: "已完成",
  failed: "失败",
};

function DocumentPanel({ documents, pending, onDelete, onProcess, onRefresh, onUpload }: DocumentPanelProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [error, setError] = useState("");
  const [processingIds, setProcessingIds] = useState<Set<number>>(() => new Set());

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setError("");
    try {
      await onUpload(file);
    } catch (err) {
      setError(err instanceof Error ? err.message : "上传失败");
    }
  }

  async function deleteDoc(document: KnowledgeDocument) {
    const confirmed = window.confirm(`确认删除文档“${document.filename}”？`);
    if (!confirmed) return;
    setError("");
    try {
      await onDelete(document);
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除失败");
    }
  }

  async function processDoc(document: KnowledgeDocument) {
    setError("");
    setProcessingIds((current) => new Set(current).add(document.id));
    try {
      await onProcess(document);
    } catch (err) {
      setError(err instanceof Error ? err.message : "处理失败");
    } finally {
      setProcessingIds((current) => {
        const next = new Set(current);
        next.delete(document.id);
        return next;
      });
    }
  }

  return (
    <section className="workspace-panel documents-panel">
      <div className="workspace-head">
        <div>
          <p className="eyebrow">Documents</p>
          <h2>文档</h2>
        </div>
        <div className="toolbar-actions">
          <button className="icon-light-button" onClick={onRefresh} disabled={pending} title="刷新">
            <RefreshCw size={16} />
          </button>
          <button className="secondary-button" onClick={() => fileInputRef.current?.click()} disabled={pending}>
            <FileUp size={16} />
            上传
          </button>
          <input ref={fileInputRef} type="file" hidden onChange={upload} />
        </div>
      </div>

      {error && <p className="form-error">{error}</p>}

      {documents.length ? (
        <div className="document-list">
          {documents.map((document) => {
            const isProcessing = processingIds.has(document.id) || document.status === "processing";
            return (
              <article className="document-row" key={document.id}>
                <div className="document-main">
                  <strong>{document.filename}</strong>
                  <span>{document.content_type || "unknown"} · {formatDate(document.updated_at)}</span>
                  {isProcessing && <span className="document-processing">正在向量化，请稍候...</span>}
                  {document.error_message && <span className="document-error">{document.error_message}</span>}
                </div>
                <span className={`status-badge status-${isProcessing ? "processing" : document.status}`}>
                  {isProcessing ? "正在向量化" : statusLabels[document.status]}
                </span>
                <div className="row-actions">
                  <button
                    className="icon-light-button"
                    onClick={() => processDoc(document)}
                    disabled={pending || isProcessing}
                    title={isProcessing ? "正在处理" : "处理"}
                  >
                    {isProcessing ? <RefreshCw size={15} className="spin" /> : <Play size={15} />}
                  </button>
                  <button
                    className="icon-light-button danger"
                    onClick={() => deleteDoc(document)}
                    disabled={pending || isProcessing}
                    title="删除"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      ) : (
        <p className="workspace-description">当前知识库还没有文档。</p>
      )}
    </section>
  );
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export default DocumentPanel;
