import { Bot, BookOpen, LibraryBig, Plus, Search, Trash2 } from "lucide-react";

import type { KnowledgeBase } from "../types";
import SiteNav from "./SiteNav";

type KnowledgeBaseListPageProps = {
  apiStatus: string;
  isAuthenticated: boolean;
  username?: string;
  knowledgeBases: KnowledgeBase[];
  pending: boolean;
  onCreateFromGazetteer: () => void;
  onAssistant: () => void;
  onHistoryAlbum: () => void;
  onFavorites: () => void;
  onHome: () => void;
  onLibrary: () => void;
  onLogin: () => void;
  onLogout: () => void;
  onDeleteKnowledgeBase: (kb: KnowledgeBase) => void;
  onOpenKnowledgeBase: (kbId: number) => void;
};

function KnowledgeBaseListPage({
  apiStatus,
  isAuthenticated,
  username,
  knowledgeBases,
  pending,
  onCreateFromGazetteer,
  onAssistant,
  onHistoryAlbum,
  onFavorites,
  onHome,
  onLibrary,
  onLogin,
  onLogout,
  onDeleteKnowledgeBase,
  onOpenKnowledgeBase,
}: KnowledgeBaseListPageProps) {
  return (
    <main className="heritage-home kb-list-page">
      <SiteNav
        active="knowledgeBase"
        isAuthenticated={isAuthenticated}
        username={username}
        onHome={onHome}
        onGazetteers={onLibrary}
        onKnowledgeBase={() => undefined}
        onAssistant={onAssistant}
        onHistoryAlbum={onHistoryAlbum}
        onFavorites={onFavorites}
        onLogin={onLogin}
        onLogout={onLogout}
      />

      <section className="catalog-hero">
        <div>
          <p className="home-eyebrow">知识库列表</p>
          <h1>一本文献，一个问答知识库</h1>
          <p>
            每个知识库对应一本文献或一个县志文件。先从县志目录下载文件，再把它加入知识库文档列表，
            处理完成后即可围绕该书进行来源可追溯的问答。
          </p>
        </div>
        <div className="catalog-summary" aria-label="知识库统计">
          <div className="catalog-summary-row">
            <span className={apiStatus === "可用" ? "status-dot ok" : "status-dot bad"} />
            <strong>{knowledgeBases.length}</strong>
            <small>知识库</small>
          </div>
          <div className="catalog-summary-row">
            <strong>{pending ? "..." : "RAG"}</strong>
            <small>状态</small>
          </div>
        </div>
      </section>

      <section className="kb-list-toolbar">
        <button className="home-primary" type="button" onClick={isAuthenticated ? onCreateFromGazetteer : onLogin}>
          <Plus size={18} />
          从县志文件创建
        </button>
        <button className="home-secondary compact" type="button" onClick={onLibrary}>
          <Search size={17} />
          浏览县志目录
        </button>
      </section>

      <section className="kb-card-grid" aria-label="知识库">
        {knowledgeBases.map((kb) => {
          const isDefaultKb = kb.name === "默认知识库";
          return (
            <article className={`kb-list-card ${isDefaultKb ? "locked" : ""}`} key={kb.id}>
              <div className="kb-list-icon">
                <BookOpen size={26} />
              </div>
              <div>
                <h2>{kb.name}</h2>
                <p>{kb.description || "由县志文件创建的独立问答知识库。"}</p>
              </div>
              <div className="gazetteer-meta">
                <span>#{kb.id}</span>
                <span>{formatDate(kb.updated_at)}</span>
                {isDefaultKb && <span>默认知识库</span>}
              </div>
              <div className="kb-card-actions">
                <button className="home-secondary compact" type="button" onClick={() => onOpenKnowledgeBase(kb.id)}>
                  <Bot size={17} />
                  进入问答
                </button>
                <button
                  className="home-secondary compact danger"
                  type="button"
                  disabled={isDefaultKb}
                  title={isDefaultKb ? "默认知识库不可删除" : "删除知识库"}
                  onClick={() => onDeleteKnowledgeBase(kb)}
                >
                  <Trash2 size={17} />
                  删除
                </button>
              </div>
            </article>
          );
        })}

        {!knowledgeBases.length && (
          <div className="kb-empty-state">
            <LibraryBig size={32} />
            <h2>还没有知识库</h2>
            <p>从县志文件创建后，系统会把下载完成的文件加入对应知识库的文档列表。</p>
            <button className="home-primary" type="button" onClick={isAuthenticated ? onCreateFromGazetteer : onLogin}>
              <Plus size={18} />
              从县志文件创建
            </button>
          </div>
        )}
      </section>
    </main>
  );
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("zh-CN");
}

export default KnowledgeBaseListPage;
