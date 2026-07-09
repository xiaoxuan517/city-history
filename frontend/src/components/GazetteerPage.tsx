import { useEffect, useState } from "react";
import {
  Bot,
  CloudDownload,
  Download,
  Eye,
  FileText,
  Landmark,
  RefreshCw,
  Search,
} from "lucide-react";

import {
  addOfflineDownload,
  getLocalDownloadFileUrl,
  getLocalDownloadPreviewUrl,
  listGazetteerFiles,
  listOfflineDownloadTasks,
} from "../api";
import type { AListTask, GazetteerFile, KnowledgeBase } from "../types";
import UserMenu from "./UserMenu";

const gazetteerPageSize = 10;
const hotRegions = ["江宁", "吴县","淮郡", "华阳", "长安", "金陵", "苏州府", "杭州府", "成都府", "常熟", "嘉定"];

type GazetteerPageProps = {
  apiStatus: string;
  isAuthenticated: boolean;
  username?: string;
  onCreateKnowledgeBaseFromDownload: (taskId: string, filename: string) => Promise<KnowledgeBase | undefined>;
  onHome: () => void;
  onAssistant: () => void;
  onHistoryAlbum: () => void;
  onKnowledgeBase: () => void;
  onLogin: () => void;
  onLogout: () => void;
  onOpenKnowledgeBase: (kbId: number) => void;
};

function GazetteerPage({
  apiStatus,
  isAuthenticated,
  username,
  onCreateKnowledgeBaseFromDownload,
  onHome,
  onAssistant,
  onHistoryAlbum,
  onKnowledgeBase,
  onLogin,
  onLogout,
  onOpenKnowledgeBase,
}: GazetteerPageProps) {
  const [items, setItems] = useState<GazetteerFile[]>([]);
  const [keyword, setKeyword] = useState("");
  const [submittedKeyword, setSubmittedKeyword] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pending, setPending] = useState(true);
  const [error, setError] = useState("");
  const [downloadTasks, setDownloadTasks] = useState<Record<string, AListTask>>({});
  const [downloadErrors, setDownloadErrors] = useState<Record<string, string>>({});
  const [knowledgeBasePending, setKnowledgeBasePending] = useState<Record<string, boolean>>({});

  useEffect(() => {
    void loadGazetteers(page, submittedKeyword);
  }, [page, submittedKeyword]);

  useEffect(() => {
    const activeTaskIds = Object.values(downloadTasks)
      .filter((task) => !isTaskFinished(task))
      .map((task) => task.id)
      .filter(Boolean);
    if (!activeTaskIds.length) return;

    const timer = window.setInterval(() => {
      void refreshDownloadTasks(activeTaskIds);
    }, 2000);
    return () => window.clearInterval(timer);
  }, [downloadTasks]);

  async function loadGazetteers(nextPage: number, q: string) {
    setPending(true);
    setError("");
    try {
      const response = await listGazetteerFiles({
        q,
        page: nextPage,
        per_page: gazetteerPageSize,
      });
      setItems(response.items);
      setTotal(response.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "县志目录加载失败");
    } finally {
      setPending(false);
    }
  }

  async function startOfflineDownload(item: GazetteerFile) {
    if (!isAuthenticated) {
      onLogin();
      return;
    }
    const cacheKey = item.full_path;
    setDownloadErrors((current) => {
      const next = { ...current };
      delete next[cacheKey];
      return next;
    });
    try {
      const response = await addOfflineDownload({
        source_path: item.source_path,
        list_path: parentPath(item.source_path),
        name: item.name,
      });
      const task = response.data.tasks[0];
      if (task) {
        setDownloadTasks((current) => ({ ...current, [cacheKey]: task }));
      }
    } catch (err) {
      setDownloadErrors((current) => ({
        ...current,
        [cacheKey]: err instanceof Error ? err.message : "添加离线下载任务失败",
      }));
    }
  }

  async function refreshDownloadTasks(taskIds: string[]) {
    try {
      const response = await listOfflineDownloadTasks(taskIds);
      if (!response.data.tasks.length) return;
      setDownloadTasks((current) => {
        const next = { ...current };
        for (const task of response.data.tasks) {
          const sourcePath = Object.keys(next).find((key) => next[key].id === task.id);
          if (sourcePath) next[sourcePath] = task;
        }
        return next;
      });
    } catch {
      // Polling failures should not interrupt browsing.
    }
  }

  async function createKnowledgeBaseFromItem(item: GazetteerFile) {
    const sourcePath = item.full_path;
    const task = downloadTasks[sourcePath] ?? downloadedTaskFromItem(item);
    const ready = task && !task.error && (task.progress >= 100 || task.state === 2);
    if (!isAuthenticated) {
      onLogin();
      return;
    }
    if (!ready) {
      setDownloadErrors((current) => ({
        ...current,
        [sourcePath]: "请先创建下载任务，等待下载完成后再加入知识库。",
      }));
      return;
    }

    setKnowledgeBasePending((current) => ({ ...current, [sourcePath]: true }));
    setDownloadErrors((current) => {
      const next = { ...current };
      delete next[sourcePath];
      return next;
    });
    try {
      const knowledgeBase = await onCreateKnowledgeBaseFromDownload(task.id, item.name);
      if (knowledgeBase) onOpenKnowledgeBase(knowledgeBase.id);
    } catch (err) {
      setDownloadErrors((current) => ({
        ...current,
        [sourcePath]: err instanceof Error ? err.message : "创建知识库失败",
      }));
    } finally {
      setKnowledgeBasePending((current) => ({ ...current, [sourcePath]: false }));
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / gazetteerPageSize));
  const pageStart = total ? (page - 1) * gazetteerPageSize + 1 : 0;
  const pageEnd = Math.min(total, page * gazetteerPageSize);

  function submitSearch() {
    setPage(1);
    setSubmittedKeyword(keyword.trim());
  }

  function searchHotRegion(region: string) {
    setKeyword(region);
    setPage(1);
    setSubmittedKeyword(region);
  }

  return (
    <main className="heritage-home gazetteer-page">
      <nav className="site-nav" aria-label="主导航">
        <button className="nav-brand" type="button" onClick={onHome}>
          <Landmark size={24} />
          <span>方志云藏</span>
        </button>
        <div className="nav-links">
          <button type="button" className="active">
            县志
          </button>
          <button type="button" onClick={onKnowledgeBase}>
            知识库
          </button>
          <button type="button" onClick={onAssistant}>
            智能助手
          </button>
          <button type="button" onClick={onHistoryAlbum}>
            历史图册
          </button>
        </div>
        <UserMenu isAuthenticated={isAuthenticated} username={username} onLogin={onLogin} onLogout={onLogout} />
      </nav>

      <section className="catalog-hero">
        <div>
          <p className="home-eyebrow">县志总目</p>
          <h1>全国地方县志古籍收藏</h1>
          <p>
            县志文件来自后台同步索引。这里集中展示具体文件，可按文件名或完整路径检索，并下载后建立 RAG
            知识库。
          </p>
        </div>
        <div className="catalog-summary" aria-label="目录统计">
          <div className="catalog-summary-row">
            <span className={apiStatus === "可用" ? "status-dot ok" : "status-dot bad"} />
            <strong>{total}</strong>
            <small>文件总数</small>
          </div>
          <div className="catalog-summary-row">
            <strong>{page}</strong>
            <small>当前页</small>
          </div>
          <div className="catalog-summary-row">
            <strong>{items.length}</strong>
            <small>本页文件</small>
          </div>
        </div>
      </section>

      <section className="catalog-search-panel" aria-label="县志筛选">
        <div className="catalog-toolbar">
          <label>
            <Search size={18} />
            <input
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") submitSearch();
              }}
              placeholder="请输入省、市、县名或古地名搜索，如 江宁、吴县、苏州府"
            />
          </label>
          <div className="catalog-toolbar-actions">
            <button
              type="button"
              className="home-secondary compact"
              disabled={pending}
              onClick={submitSearch}
            >
              <Search size={17} />
              检索
            </button>
            <button
              type="button"
              className="home-secondary compact"
              disabled={pending}
              onClick={() => void loadGazetteers(page, submittedKeyword)}
            >
              <RefreshCw size={17} className={pending ? "spin" : undefined} />
              刷新
            </button>
          </div>
        </div>
        <div className="hot-region-tags" aria-label="热门地名">
          {hotRegions.map((region) => (
            <button key={region} type="button" onClick={() => searchHotRegion(region)}>
              {region}
            </button>
          ))}
        </div>
      </section>

      {error && (
        <section className="catalog-state error">
          <p>{error}</p>
        </section>
      )}

      {pending && !error && (
        <section className="catalog-state">
          <p>正在加载县志目录...</p>
        </section>
      )}

      {!pending && !error && (
        <section className="gazetteer-list" aria-label="县志目录列表">
          <div className="catalog-page-info">
            <span>
              共 {total} 个文件，当前显示 {pageStart}-{pageEnd}
            </span>
            <div className="catalog-pagination">
              <button
                type="button"
                className="home-secondary compact"
                disabled={page <= 1}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
              >
                上一页
              </button>
              <span>
                {page} / {totalPages}
              </span>
              <button
                type="button"
                className="home-secondary compact"
                disabled={page >= totalPages}
                onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
              >
                下一页
              </button>
            </div>
          </div>

          {items.map((item) => (
            <GazetteerRow
              key={item.id}
              item={item}
              downloadError={downloadErrors[item.full_path]}
              downloadTask={downloadTasks[item.full_path] ?? downloadedTaskFromItem(item)}
              knowledgeBasePending={Boolean(knowledgeBasePending[item.full_path])}
              pending={pending}
              isAuthenticated={isAuthenticated}
              onLogin={onLogin}
              onKnowledgeBase={createKnowledgeBaseFromItem}
              onStartDownload={startOfflineDownload}
            />
          ))}

          {!items.length && (
            <div className="catalog-state">
              <p>没有匹配的县志条目。</p>
            </div>
          )}
        </section>
      )}
    </main>
  );
}

function GazetteerRow({
  item,
  downloadError,
  downloadTask,
  knowledgeBasePending,
  pending,
  isAuthenticated,
  onLogin,
  onKnowledgeBase,
  onStartDownload,
}: {
  item: GazetteerFile;
  downloadError?: string;
  downloadTask?: AListTask;
  knowledgeBasePending: boolean;
  pending: boolean;
  isAuthenticated: boolean;
  onLogin: () => void;
  onKnowledgeBase: (item: GazetteerFile) => void;
  onStartDownload: (item: GazetteerFile) => void;
}) {
  const sourcePath = item.full_path;
  const downloadPending = Boolean(downloadTask && !isTaskFinished(downloadTask));
  const canDownloadLocal = Boolean(
    downloadTask && !downloadTask.error && (downloadTask.progress >= 100 || downloadTask.state === 2),
  );

  return (
    <article className="gazetteer-card">
      <div className="gazetteer-icon"><FileText size={28} /></div>
      <div className="gazetteer-main">
        <h2>{item.name}</h2>
        <p>{item.full_path}</p>
        <div className="gazetteer-meta">
          <span>文件</span>
          <span>{formatSize(item.size)}</span>
          <span>{formatDate(item.modified)}</span>
          {downloadTask && <span>{taskLabel(downloadTask)}</span>}
        </div>
        {downloadTask && (
          <div className="download-progress">
            <span style={{ width: `${Math.max(0, Math.min(100, downloadTask.progress || 0))}%` }} />
          </div>
        )}
        {downloadError && <p className="download-error">{downloadError}</p>}
      </div>
      <div className="gazetteer-actions">
        <button
          type="button"
          className="text-action"
          title="创建下载任务"
          disabled={downloadPending || canDownloadLocal}
          onClick={() => onStartDownload(item)}
        >
          <CloudDownload size={16} />
          <span>创建下载任务</span>
        </button>
        <button
          type="button"
          className="text-action"
          title="下载到本地"
          disabled={!canDownloadLocal}
          onClick={() => {
            if (!isAuthenticated) {
              onLogin();
              return;
            }
            if (downloadTask) window.location.href = getLocalDownloadFileUrl(downloadTask.id);
          }}
        >
          <Download size={16} />
          <span>下载到本地</span>
        </button>
        <button
          type="button"
          className="text-action"
          title="在线预览"
          disabled={!canDownloadLocal}
          onClick={() => {
            if (!isAuthenticated) {
              onLogin();
              return;
            }
            if (downloadTask) window.open(getLocalDownloadPreviewUrl(downloadTask.id), "_blank", "noopener,noreferrer");
          }}
        >
          <Eye size={16} />
          <span>在线预览</span>
        </button>
        <button
          type="button"
          title={canDownloadLocal ? "加入知识库问答" : "请先下载"}
          disabled={knowledgeBasePending}
          onClick={() => onKnowledgeBase(item)}
        >
          <Bot size={17} />
        </button>
      </div>
    </article>
  );
}

function formatSize(size: number) {
  if (!size) return "-";
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  if (size < 1024 * 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`;
  return `${(size / 1024 / 1024 / 1024).toFixed(1)} GB`;
}

function formatDate(value: string) {
  if (!value) return "未记录时间";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("zh-CN");
}

function parentPath(path: string) {
  const normalized = path.replace(/\/$/, "");
  return normalized.slice(0, normalized.lastIndexOf("/")) || "/";
}

function isTaskFinished(task: AListTask) {
  return Boolean(task.error) || task.progress >= 100 || task.state === 2 || task.state < 0;
}

function downloadedTaskFromItem(item: GazetteerFile): AListTask | undefined {
  if (!item.is_downloaded || !item.local_download_task_id) return undefined;
  return {
    id: item.local_download_task_id,
    name: `downloaded file ${item.name}`,
    state: 2,
    status: "已保存到 downloads 目录",
    progress: 100,
    error: "",
  };
}

function taskLabel(task: AListTask) {
  if (task.error) return "下载失败";
  if (task.progress >= 100 || task.state === 2) return "下载完成";
  return `下载中 ${task.progress || 0}%`;
}

export default GazetteerPage;
