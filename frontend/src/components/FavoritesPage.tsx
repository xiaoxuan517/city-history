import { useEffect, useState } from "react";
import {
  Bot,
  BookOpen,
  CloudDownload,
  Download,
  Eye,
  FileText,
  ImageIcon,
  Star,
  Trash2,
  X,
} from "lucide-react";

import {
  addOfflineDownload,
  getLocalDownloadFileUrl,
  getLocalDownloadPreviewUrl,
  getOldPicturePreviewUrl,
  listOfflineDownloadTasks,
} from "../api";
import {
  type FavoriteGazetteer,
  type FavoriteOldPicture,
  loadFavoriteGazetteers,
  loadFavoriteOldPictures,
  removeFavoriteGazetteer,
  removeFavoriteOldPicture,
} from "../favorites";
import type { AListTask, KnowledgeBase } from "../types";
import SiteNav from "./SiteNav";

type FavoritesPageProps = {
  apiStatus: string;
  isAuthenticated: boolean;
  username?: string;
  onCreateKnowledgeBaseFromDownload: (taskId: string, filename: string) => Promise<KnowledgeBase | undefined>;
  onHome: () => void;
  onGazetteers: () => void;
  onKnowledgeBase: () => void;
  onAssistant: () => void;
  onHistoryAlbum: () => void;
  onLogin: () => void;
  onLogout: () => void;
  onOpenKnowledgeBase: (kbId: number) => void;
};

function FavoritesPage({
  apiStatus,
  isAuthenticated,
  username,
  onCreateKnowledgeBaseFromDownload,
  onHome,
  onGazetteers,
  onKnowledgeBase,
  onAssistant,
  onHistoryAlbum,
  onLogin,
  onLogout,
  onOpenKnowledgeBase,
}: FavoritesPageProps) {
  const [activeTab, setActiveTab] = useState<"gazetteers" | "pictures">("gazetteers");
  const [gazetteers, setGazetteers] = useState<FavoriteGazetteer[]>(() => loadFavoriteGazetteers());
  const [pictures, setPictures] = useState<FavoriteOldPicture[]>(() => loadFavoriteOldPictures());
  const [previewPicture, setPreviewPicture] = useState<FavoriteOldPicture | null>(null);
  const [downloadTasks, setDownloadTasks] = useState<Record<string, AListTask>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [knowledgeBasePending, setKnowledgeBasePending] = useState<Record<string, boolean>>({});

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

  async function startGazetteerDownload(item: FavoriteGazetteer) {
    if (!isAuthenticated) {
      onLogin();
      return;
    }
    setErrors((current) => {
      const next = { ...current };
      delete next[item.full_path];
      return next;
    });
    try {
      const response = await addOfflineDownload({
        source_path: item.source_path,
        list_path: parentPath(item.source_path),
        name: item.name,
      });
      const task = response.data.tasks[0];
      if (task) setDownloadTasks((current) => ({ ...current, [item.full_path]: task }));
    } catch (error) {
      setErrors((current) => ({
        ...current,
        [item.full_path]: error instanceof Error ? error.message : "创建下载任务失败",
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
      // Polling failures should not interrupt the favorites page.
    }
  }

  async function createKnowledgeBaseFromItem(item: FavoriteGazetteer) {
    const task = downloadTasks[item.full_path] ?? downloadedTaskFromGazetteer(item);
    const ready = task && !task.error && (task.progress >= 100 || task.state === 2);
    if (!isAuthenticated) {
      onLogin();
      return;
    }
    if (!ready) {
      setErrors((current) => ({
        ...current,
        [item.full_path]: "请先创建下载任务，等待下载完成后再加入知识库。",
      }));
      return;
    }

    setKnowledgeBasePending((current) => ({ ...current, [item.full_path]: true }));
    try {
      const knowledgeBase = await onCreateKnowledgeBaseFromDownload(task.id, item.name);
      if (knowledgeBase) onOpenKnowledgeBase(knowledgeBase.id);
    } catch (error) {
      setErrors((current) => ({
        ...current,
        [item.full_path]: error instanceof Error ? error.message : "创建知识库失败",
      }));
    } finally {
      setKnowledgeBasePending((current) => ({ ...current, [item.full_path]: false }));
    }
  }

  function removeGazetteer(fullPath: string) {
    removeFavoriteGazetteer(fullPath);
    setGazetteers(loadFavoriteGazetteers());
  }

  function removePicture(taskId: string) {
    removeFavoriteOldPicture(taskId);
    setPictures(loadFavoriteOldPictures());
    if (previewPicture?.local_download_task_id === taskId) setPreviewPicture(null);
  }

  return (
    <main className="heritage-home favorites-page">
      <SiteNav
        active="favorites"
        isAuthenticated={isAuthenticated}
        username={username}
        onHome={onHome}
        onGazetteers={onGazetteers}
        onKnowledgeBase={onKnowledgeBase}
        onAssistant={onAssistant}
        onHistoryAlbum={onHistoryAlbum}
        onFavorites={() => undefined}
        onLogin={onLogin}
        onLogout={onLogout}
      />

      <section className="catalog-hero">
        <div>
          <p className="home-eyebrow">我的收藏</p>
          <h1>随手收起重要的县志与图片</h1>
          <p>
            把常看的县志和历史图片集中放在这里，便于再次阅读、下载、预览，或继续围绕县志创建问答知识库。
          </p>
        </div>
        <div className="catalog-summary" aria-label="收藏统计">
          <div className="catalog-summary-row">
            <span className={apiStatus === "可用" ? "status-dot ok" : "status-dot bad"} />
            <strong>{gazetteers.length}</strong>
            <small>县志收藏</small>
          </div>
          <div className="catalog-summary-row">
            <strong>{pictures.length}</strong>
            <small>图片收藏</small>
          </div>
        </div>
      </section>

      <section className="favorites-tabs" aria-label="收藏分类">
        <button
          type="button"
          className={activeTab === "gazetteers" ? "active" : undefined}
          onClick={() => setActiveTab("gazetteers")}
        >
          <BookOpen size={17} />
          县志收藏
        </button>
        <button
          type="button"
          className={activeTab === "pictures" ? "active" : undefined}
          onClick={() => setActiveTab("pictures")}
        >
          <ImageIcon size={17} />
          历史图片收藏
        </button>
      </section>

      {activeTab === "gazetteers" ? (
        <section className="gazetteer-list" aria-label="县志收藏列表">
          {gazetteers.map((item) => {
            const task = downloadTasks[item.full_path] ?? downloadedTaskFromGazetteer(item);
            return (
              <article className="gazetteer-card" key={item.full_path}>
                <div className="gazetteer-icon">
                  <FileText size={28} />
                </div>
                <div className="gazetteer-main">
                  <h2>{item.name}</h2>
                  <p>{item.full_path}</p>
                  <div className="gazetteer-meta">
                    <span>文件</span>
                    <span>{formatSize(item.size)}</span>
                    <span>{formatDate(item.modified)}</span>
                    <span>收藏于 {formatDate(item.favorited_at)}</span>
                    {task && <span>{taskLabel(task)}</span>}
                  </div>
                  {task && (
                    <div className="download-progress">
                      <span style={{ width: `${Math.max(0, Math.min(100, task.progress || 0))}%` }} />
                    </div>
                  )}
                  {errors[item.full_path] && <p className="download-error">{errors[item.full_path]}</p>}
                </div>
                <div className="gazetteer-actions">
                  <button
                    type="button"
                    className="text-action active-favorite"
                    title="取消收藏"
                    onClick={() => removeGazetteer(item.full_path)}
                  >
                    <Star size={16} fill="currentColor" />
                    <span>已收藏</span>
                  </button>
                  <button
                    type="button"
                    className="text-action"
                    title="创建下载任务"
                    disabled={Boolean(task && !isTaskFinished(task)) || canUseTask(task)}
                    onClick={() => startGazetteerDownload(item)}
                  >
                    <CloudDownload size={16} />
                    <span>创建下载任务</span>
                  </button>
                  <button
                    type="button"
                    className="text-action"
                    title="下载到本地"
                    disabled={!canUseTask(task)}
                    onClick={() => {
                      if (!isAuthenticated) {
                        onLogin();
                        return;
                      }
                      if (task) window.location.href = getLocalDownloadFileUrl(task.id);
                    }}
                  >
                    <Download size={16} />
                    <span>下载到本地</span>
                  </button>
                  <button
                    type="button"
                    className="text-action"
                    title="在线预览"
                    disabled={!canUseTask(task)}
                    onClick={() => {
                      if (!isAuthenticated) {
                        onLogin();
                        return;
                      }
                      if (task) window.open(getLocalDownloadPreviewUrl(task.id), "_blank", "noopener,noreferrer");
                    }}
                  >
                    <Eye size={16} />
                    <span>在线预览</span>
                  </button>
                  <button
                    type="button"
                    title={canUseTask(task) ? "加入知识库问答" : "请先下载"}
                    disabled={Boolean(knowledgeBasePending[item.full_path])}
                    onClick={() => createKnowledgeBaseFromItem(item)}
                  >
                    <Bot size={17} />
                  </button>
                </div>
              </article>
            );
          })}
          {!gazetteers.length && (
            <div className="catalog-state">
              <p>还没有收藏县志。可以在县志目录中点击收藏。</p>
            </div>
          )}
        </section>
      ) : (
        <section className="local-picture-section favorites-picture-section" aria-label="历史图片收藏瀑布流">
          {pictures.length ? (
            <div className="picture-masonry">
              {pictures.map((picture) => (
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
                    <span>收藏于 {formatDate(picture.favorited_at)}</span>
                    <button
                      className="home-secondary compact picture-download-button active-favorite"
                      type="button"
                      onClick={() => removePicture(picture.local_download_task_id)}
                    >
                      <Trash2 size={15} />
                      取消收藏
                    </button>
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
          ) : (
            <div className="catalog-state">
              <p>还没有收藏历史图片。可以在历史图册的本地图册瀑布流中点击收藏。</p>
            </div>
          )}
        </section>
      )}

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
    </main>
  );
}

function parentPath(path: string) {
  const normalized = path.replace(/\/$/, "");
  return normalized.slice(0, normalized.lastIndexOf("/")) || "/";
}

function canUseTask(task?: AListTask) {
  return Boolean(task && !task.error && (task.progress >= 100 || task.state === 2));
}

function isTaskFinished(task: AListTask) {
  return Boolean(task.error) || task.progress >= 100 || task.state === 2 || task.state < 0;
}

function downloadedTaskFromGazetteer(item: FavoriteGazetteer): AListTask | undefined {
  if (!item.is_downloaded || !item.local_download_task_id) return undefined;
  return {
    id: item.local_download_task_id,
    name: `downloaded file ${item.name}`,
    state: 2,
    status: "已下载完成",
    progress: 100,
    error: "",
  };
}

function taskLabel(task: AListTask) {
  if (task.error) return "下载失败";
  if (task.progress >= 100 || task.state === 2) return "下载完成";
  return `下载中 ${task.progress || 0}%`;
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

export default FavoritesPage;
