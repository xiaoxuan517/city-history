import { useEffect, useState } from "react";
import {
  CloudDownload,
  Download,
  Eye,
  ImageIcon,
  RefreshCw,
  Search,
  X,
} from "lucide-react";

import {
  addOfflineDownload,
  getLocalDownloadFileUrl,
  getLocalDownloadPreviewUrl,
  getOldPicturePreviewUrl,
  listLocalOldPictures,
  listOfflineDownloadTasks,
  listOldPictures,
} from "../api";
import type { AListTask, LocalOldPicture, OldPicture } from "../types";
import SiteNav from "./SiteNav";

const picturePageSize = 12;
const localLoadSize = 20;
const pictureTags = ["民国人物", "抗战影像", "旧城街景", "铁路", "学校", "码头", "商铺", "建筑", "军政", "家庭合影"];

type HistoryAlbumPageProps = {
  apiStatus: string;
  isAuthenticated: boolean;
  username?: string;
  onHome: () => void;
  onGazetteers: () => void;
  onKnowledgeBase: () => void;
  onAssistant: () => void;
  onLogin: () => void;
  onLogout: () => void;
};

function HistoryAlbumPage({
  apiStatus,
  isAuthenticated,
  username,
  onHome,
  onGazetteers,
  onKnowledgeBase,
  onAssistant,
  onLogin,
  onLogout,
}: HistoryAlbumPageProps) {
  const [localPictures, setLocalPictures] = useState<LocalOldPicture[]>([]);
  const [localTotal, setLocalTotal] = useState(0);
  const [localPending, setLocalPending] = useState(true);
  const [items, setItems] = useState<OldPicture[]>([]);
  const [keyword, setKeyword] = useState("");
  const [submittedKeyword, setSubmittedKeyword] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pending, setPending] = useState(true);
  const [error, setError] = useState("");
  const [downloadTasks, setDownloadTasks] = useState<Record<string, AListTask>>({});
  const [downloadErrors, setDownloadErrors] = useState<Record<string, string>>({});
  const [previewPicture, setPreviewPicture] = useState<LocalOldPicture | null>(null);

  useEffect(() => {
    void loadLocalPictures(0);
    void loadPictures(page, submittedKeyword);
  }, []);

  useEffect(() => {
    if (page === 1 && !submittedKeyword) return;
    void loadPictures(page, submittedKeyword);
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

  useEffect(() => {
    if (!previewPicture) return;
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setPreviewPicture(null);
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [previewPicture]);

  async function loadLocalPictures(offset: number) {
    setLocalPending(true);
    try {
      const response = await listLocalOldPictures({ offset, limit: localLoadSize });
      setLocalPictures((current) => (offset === 0 ? response.items : [...current, ...response.items]));
      setLocalTotal(response.total);
    } finally {
      setLocalPending(false);
    }
  }

  async function loadPictures(nextPage: number, q: string) {
    setPending(true);
    setError("");
    try {
      const response = await listOldPictures({
        q,
        page: nextPage,
        per_page: picturePageSize,
      });
      setItems(response.items);
      setTotal(response.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "历史图册加载失败");
    } finally {
      setPending(false);
    }
  }

  async function startOfflineDownload(item: OldPicture) {
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
        path: "picture",
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
        [cacheKey]: err instanceof Error ? err.message : "创建图片下载任务失败",
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

  function submitSearch() {
    setPage(1);
    setSubmittedKeyword(keyword.trim());
  }

  function searchTag(tag: string) {
    setKeyword(tag);
    setPage(1);
    setSubmittedKeyword(tag);
  }

  const totalPages = Math.max(1, Math.ceil(total / picturePageSize));
  const pageStart = total ? (page - 1) * picturePageSize + 1 : 0;
  const pageEnd = Math.min(total, page * picturePageSize);

  return (
    <main className="heritage-home history-album-page">
      <SiteNav
        active="historyAlbum"
        isAuthenticated={isAuthenticated}
        username={username}
        onHome={onHome}
        onGazetteers={onGazetteers}
        onKnowledgeBase={onKnowledgeBase}
        onAssistant={onAssistant}
        onHistoryAlbum={() => undefined}
        onLogin={onLogin}
        onLogout={onLogout}
      />

      <section className="catalog-hero">
        <div>
          <p className="home-eyebrow">历史图册</p>
          <h1>一万张历史老照片</h1>
          <p>
            图片元数据来自 AList 网盘同步索引，支持按图片名和完整路径检索。已下载图片保存在服务器
            picture 目录，可在线预览或下载到本地。
          </p>
        </div>
        <div className="catalog-summary" aria-label="图册统计">
          <div className="catalog-summary-row">
            <span className={apiStatus === "可用" ? "status-dot ok" : "status-dot bad"} />
            <strong>{total}</strong>
            <small>图片索引</small>
          </div>
          <div className="catalog-summary-row">
            <strong>{localTotal}</strong>
            <small>已下载</small>
          </div>
          <div className="catalog-summary-row">
            <strong>{page}</strong>
            <small>当前页</small>
          </div>
        </div>
      </section>

      <section className="local-picture-section" aria-label="已下载图片瀑布流">
        <div className="section-head split">
          <div>
            <p className="home-eyebrow">本地图册</p>
            <h2>已下载的图片</h2>
          </div>
          <button
            className="home-secondary compact"
            type="button"
            disabled={localPending}
            onClick={() => void loadLocalPictures(0)}
          >
            <RefreshCw size={17} className={localPending ? "spin" : undefined} />
            刷新
          </button>
        </div>

        {localPictures.length > 0 ? (
          <>
            <div className="picture-masonry">
              {localPictures.map((picture) => (
                <article className="picture-tile" key={picture.local_download_task_id}>
                  <button
                    className="picture-preview-button"
                    type="button"
                    onClick={() => setPreviewPicture(picture)}
                  >
                    <img
                      src={getOldPicturePreviewUrl(picture.preview_name)}
                      alt={picture.name}
                      loading="lazy"
                      decoding="async"
                    />
                  </button>
                  <div className="picture-tile-body">
                    <strong>{picture.name}</strong>
                    <span>{formatSize(picture.size)}</span>
                    <button
                      className="home-secondary compact picture-download-button"
                      type="button"
                      onClick={() => {
                        window.location.href = getLocalDownloadFileUrl(picture.local_download_task_id);
                      }}
                    >
                      <Download size={15} />
                      下载到本地
                    </button>
                  </div>
                </article>
              ))}
            </div>
            {localPictures.length < localTotal && (
              <button
                className="home-secondary compact load-more-pictures"
                type="button"
                disabled={localPending}
                onClick={() => void loadLocalPictures(localPictures.length)}
              >
                加载更多
              </button>
            )}
          </>
        ) : (
          <div className="catalog-state">
            <p>{localPending ? "正在读取本地图册..." : "picture 目录下还没有已下载图片。"}</p>
          </div>
        )}
      </section>

      {previewPicture && (
        <div className="picture-preview-overlay" role="dialog" aria-modal="true" aria-label="图片预览">
          <button className="picture-preview-backdrop" type="button" onClick={() => setPreviewPicture(null)} />
          <div className="picture-preview-dialog">
            <div className="picture-preview-header">
              <strong>{previewPicture.name}</strong>
              <div>
                <button
                  className="home-secondary compact"
                  type="button"
                  onClick={() => {
                    window.location.href = getLocalDownloadFileUrl(previewPicture.local_download_task_id);
                  }}
                >
                  <Download size={16} />
                  下载到本地
                </button>
                <button
                  className="icon-button light"
                  type="button"
                  title="关闭预览"
                  onClick={() => setPreviewPicture(null)}
                >
                  <X size={18} />
                </button>
              </div>
            </div>
            <img src={getLocalDownloadPreviewUrl(previewPicture.local_download_task_id)} alt={previewPicture.name} />
          </div>
        </div>
      )}

      <section className="catalog-search-panel" aria-label="历史图片筛选">
        <div className="catalog-toolbar">
          <label>
            <Search size={18} />
            <input
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") submitSearch();
              }}
              placeholder="输入图片名、人物、地点、事件或路径搜索，如 民国、铁路、学校"
            />
          </label>
          <div className="catalog-toolbar-actions">
            <button type="button" className="home-secondary compact" disabled={pending} onClick={submitSearch}>
              <Search size={17} />
              检索
            </button>
            <button
              type="button"
              className="home-secondary compact"
              disabled={pending}
              onClick={() => void loadPictures(page, submittedKeyword)}
            >
              <RefreshCw size={17} className={pending ? "spin" : undefined} />
              刷新
            </button>
          </div>
        </div>
        <div className="hot-region-tags" aria-label="图片标签">
          {pictureTags.map((tag) => (
            <button key={tag} type="button" onClick={() => searchTag(tag)}>
              {tag}
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
          <p>正在加载历史图片目录...</p>
        </section>
      )}

      {!pending && !error && (
        <section className="picture-result-list" aria-label="历史图片目录列表">
          <div className="catalog-page-info">
            <span>
              共 {total} 张图片，当前显示 {pageStart}-{pageEnd}
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
            <PictureRow
              key={item.id}
              item={item}
              downloadError={downloadErrors[item.full_path]}
              downloadTask={downloadTasks[item.full_path] ?? downloadedTaskFromItem(item)}
              isAuthenticated={isAuthenticated}
              onLogin={onLogin}
              onStartDownload={startOfflineDownload}
            />
          ))}

          {!items.length && (
            <div className="catalog-state">
              <p>没有匹配的历史图片。</p>
            </div>
          )}
        </section>
      )}
    </main>
  );
}

function PictureRow({
  item,
  downloadError,
  downloadTask,
  isAuthenticated,
  onLogin,
  onStartDownload,
}: {
  item: OldPicture;
  downloadError?: string;
  downloadTask?: AListTask;
  isAuthenticated: boolean;
  onLogin: () => void;
  onStartDownload: (item: OldPicture) => void;
}) {
  const downloadPending = Boolean(downloadTask && !isTaskFinished(downloadTask));
  const canDownloadLocal = Boolean(
    downloadTask && !downloadTask.error && (downloadTask.progress >= 100 || downloadTask.state === 2),
  );

  return (
    <article className="gazetteer-card picture-result-card">
      <div className="gazetteer-icon">
        <ImageIcon size={28} />
      </div>
      <div className="gazetteer-main">
        <h2>{item.name}</h2>
        <p>{item.full_path}</p>
        <div className="gazetteer-meta">
          <span>图片</span>
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
          <span>预览</span>
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

function downloadedTaskFromItem(item: OldPicture): AListTask | undefined {
  if (!item.is_downloaded || !item.local_download_task_id) return undefined;
  return {
    id: item.local_download_task_id,
    name: `downloaded file ${item.name}`,
    state: 2,
    status: "已保存到 picture 目录",
    progress: 100,
    error: "",
  };
}

function taskLabel(task: AListTask) {
  if (task.error) return "下载失败";
  if (task.progress >= 100 || task.state === 2) return "下载完成";
  return `下载中 ${task.progress || 0}%`;
}

export default HistoryAlbumPage;
