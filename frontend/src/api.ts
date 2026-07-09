import type {
  KnowledgeBase,
  KnowledgeBaseWithDocumentResponse,
  AssistantChatResponse,
  AListFileListResponse,
  AListOfflineDownloadResponse,
  AListTaskListResponse,
  GazetteerFileListResponse,
  LocalOldPictureListResponse,
  ChatRun,
  ChatRunEvent,
  ChatSession,
  KnowledgeDocument,
  OldPictureListResponse,
  PublicConfig,
  RetrievalPreviewResponse,
  RetrievalProfile,
  StreamEvent,
  StoredChatMessage,
  TokenResponse,
  User,
} from "./types";

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
const gazetteerFileRequests = new Map<string, Promise<GazetteerFileListResponse>>();
const oldPictureRequests = new Map<string, Promise<OldPictureListResponse>>();
const authNoticeStorageKey = "rag_auth_notice";
const tokenStorageKey = "rag_access_token";
const userStorageKey = "rag_current_user";

export class ApiRequestError extends Error {
  status: number;
  code?: string;

  constructor(message: string, options: { status: number; code?: string }) {
    super(message);
    this.name = "ApiRequestError";
    this.status = options.status;
    this.code = options.code;
  }
}

export function isUnauthorizedApiError(error: unknown) {
  return error instanceof ApiRequestError && error.status === 401;
}

function apiUrl(path: string) {
  return `${apiBaseUrl}${path}`;
}

export function getLocalDownloadFileUrl(taskId: string) {
  return apiUrl(`/api/fs/offline_download/tasks/${encodeURIComponent(taskId)}/file`);
}

export function getLocalDownloadPreviewUrl(taskId: string) {
  return apiUrl(`/api/fs/offline_download/tasks/${encodeURIComponent(taskId)}/preview`);
}

export function getOldPicturePreviewUrl(filename: string) {
  return apiUrl(`/api/v1/old-pictures/local-preview/${encodeURIComponent(filename)}`);
}

async function request(path: string, options: RequestInit = {}, token?: string) {
  const response = await fetch(apiUrl(path), {
    ...options,
    headers: {
      ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const detail = payload.detail || payload.error?.message || `HTTP ${response.status}`;
    const code = payload.error?.code;
    if (response.status === 401 && token) {
      localStorage.removeItem(tokenStorageKey);
      localStorage.removeItem(userStorageKey);
      sessionStorage.setItem(authNoticeStorageKey, "登录已过期，请重新登录。");
      window.dispatchEvent(new CustomEvent("rag:auth-expired"));
      if (!window.location.pathname.startsWith("/login")) {
        window.history.pushState(null, "", "/login");
        window.dispatchEvent(new PopStateEvent("popstate"));
      }
    }
    throw new ApiRequestError(detail, { status: response.status, code });
  }
  return response;
}

async function postJson(path: string, body: unknown = {}, token?: string) {
  return request(
    path,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
    token,
  );
}

export async function checkHealth() {
  const response = await fetch(apiUrl("/api/v1/health"));
  return response.ok;
}

export async function loadConfig(): Promise<PublicConfig> {
  const response = await fetch(apiUrl("/api/v1/config"));
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

export async function registerUser(payload: {
  username: string;
  email: string;
  password: string;
}): Promise<User> {
  const response = await postJson("/api/v1/auth/register", payload);
  return response.json();
}

export async function loginUser(payload: {
  username_or_email: string;
  password: string;
}): Promise<TokenResponse> {
  const response = await postJson("/api/v1/auth/login", payload);
  return response.json();
}

export async function loadMe(token: string): Promise<User> {
  const response = await request("/api/v1/auth/me", {}, token);
  return response.json();
}

export async function listKnowledgeBases(token: string): Promise<KnowledgeBase[]> {
  const response = await request("/api/v1/kbs", {}, token);
  return response.json();
}

export async function createKnowledgeBase(
  token: string,
  payload: { name: string; description?: string },
): Promise<KnowledgeBase> {
  const response = await postJson("/api/v1/kbs", payload, token);
  return response.json();
}

export async function createKnowledgeBaseFromDownload(
  token: string,
  payload: { task_id: string; name: string; description?: string },
): Promise<KnowledgeBaseWithDocumentResponse> {
  const response = await postJson("/api/v1/kbs/from-download", payload, token);
  return response.json();
}

export async function updateKnowledgeBase(
  token: string,
  kbId: number,
  payload: { name?: string; description?: string },
): Promise<KnowledgeBase> {
  const response = await request(
    `/api/v1/kbs/${kbId}`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
    },
    token,
  );
  return response.json();
}

export async function deleteKnowledgeBase(token: string, kbId: number): Promise<void> {
  await request(`/api/v1/kbs/${kbId}`, { method: "DELETE" }, token);
}

export async function listDocuments(token: string, kbId: number): Promise<KnowledgeDocument[]> {
  const response = await request(`/api/v1/kbs/${kbId}/documents`, {}, token);
  return response.json();
}

export async function getDocument(token: string, documentId: number): Promise<KnowledgeDocument> {
  const response = await request(`/api/v1/documents/${documentId}`, {}, token);
  return response.json();
}

export async function uploadDocument(token: string, kbId: number, file: File): Promise<KnowledgeDocument> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await request(
    `/api/v1/kbs/${kbId}/documents`,
    {
      method: "POST",
      body: formData,
    },
    token,
  );
  return response.json();
}

export async function processDocument(token: string, documentId: number): Promise<{ document: KnowledgeDocument }> {
  const response = await postJson(`/api/v1/documents/${documentId}/process`, {}, token);
  return response.json();
}

export async function deleteDocument(token: string, documentId: number): Promise<void> {
  await request(`/api/v1/documents/${documentId}`, { method: "DELETE" }, token);
}

export async function cancelChatRun(token: string, runId: number): Promise<{ run_id: number; cancelled: boolean }> {
  const response = await postJson(`/api/v1/chat-runs/${runId}/cancel`, {}, token);
  return response.json();
}

export async function getChatRun(token: string, runId: number): Promise<ChatRun> {
  const response = await request(`/api/v1/chat-runs/${runId}`, {}, token);
  return response.json();
}

export async function listChatRunEvents(token: string, runId: number): Promise<ChatRunEvent[]> {
  const response = await request(`/api/v1/chat-runs/${runId}/events`, {}, token);
  return response.json();
}

export async function listChatSessions(token: string): Promise<ChatSession[]> {
  const response = await request("/api/v1/chat-sessions", {}, token);
  return response.json();
}

export async function listChatMessages(token: string, sessionId: number): Promise<StoredChatMessage[]> {
  const response = await request(`/api/v1/chat-sessions/${sessionId}/messages`, {}, token);
  return response.json();
}

export async function deleteChatSession(token: string, sessionId: number): Promise<void> {
  await request(`/api/v1/chat-sessions/${sessionId}`, { method: "DELETE" }, token);
}

export async function chatWithAssistant(
  token: string,
  payload: { message: string; state?: Record<string, unknown> },
): Promise<AssistantChatResponse> {
  const response = await postJson(
    "/api/v1/assistant/chat",
    { message: payload.message, state: payload.state ?? {} },
    token,
  );
  return response.json();
}

export async function listAListFiles(payload: {
  path?: string;
  password?: string;
  page?: number;
  per_page?: number;
  refresh?: boolean;
} = {}): Promise<AListFileListResponse> {
  const response = await postJson("/api/fs/list", {
    path: payload.path ?? "/百度网盘/全国地方县志古籍收藏",
    password: payload.password ?? "",
    page: payload.page ?? 1,
    per_page: payload.per_page ?? 100,
    refresh: payload.refresh ?? false,
  });
  return response.json();
}

export async function listGazetteerFiles(payload: {
  q?: string;
  page?: number;
  per_page?: number;
} = {}): Promise<GazetteerFileListResponse> {
  const params = new URLSearchParams({
    q: payload.q ?? "",
    page: String(payload.page ?? 1),
    per_page: String(payload.per_page ?? 10),
  });
  const requestKey = params.toString();
  const pendingRequest = gazetteerFileRequests.get(requestKey);
  if (pendingRequest) return pendingRequest;

  const nextRequest = request(`/api/v1/gazetteer-files?${requestKey}`)
    .then((response) => response.json())
    .finally(() => {
      gazetteerFileRequests.delete(requestKey);
    });
  gazetteerFileRequests.set(requestKey, nextRequest);
  return nextRequest;
}

export async function listOldPictures(payload: {
  q?: string;
  page?: number;
  per_page?: number;
} = {}): Promise<OldPictureListResponse> {
  const params = new URLSearchParams({
    q: payload.q ?? "",
    page: String(payload.page ?? 1),
    per_page: String(payload.per_page ?? 12),
  });
  const requestKey = params.toString();
  const pendingRequest = oldPictureRequests.get(requestKey);
  if (pendingRequest) return pendingRequest;

  const nextRequest = request(`/api/v1/old-pictures?${requestKey}`)
    .then((response) => response.json())
    .finally(() => {
      oldPictureRequests.delete(requestKey);
    });
  oldPictureRequests.set(requestKey, nextRequest);
  return nextRequest;
}

export async function listLocalOldPictures(payload: {
  offset?: number;
  limit?: number;
} = {}): Promise<LocalOldPictureListResponse> {
  const params = new URLSearchParams({
    offset: String(payload.offset ?? 0),
    limit: String(payload.limit ?? 20),
  });
  const response = await request(`/api/v1/old-pictures/local?${params.toString()}`);
  return response.json();
}

export async function addOfflineDownload(payload: {
  path?: string;
  urls?: string[];
  source_path?: string;
  list_path?: string;
  name?: string;
  tool?: "aria2" | "SimpleHttp" | "qBittorrent";
  delete_policy?: "delete_on_upload_succeed" | "delete_on_upload_failed" | "delete_never" | "delete_always";
}): Promise<AListOfflineDownloadResponse> {
  const response = await postJson("/api/fs/add_offline_download", {
    path: payload.path ?? "downloads",
    urls: payload.urls,
    source_path: payload.source_path,
    list_path: payload.list_path,
    name: payload.name,
    tool: payload.tool ?? "SimpleHttp",
    delete_policy: payload.delete_policy ?? "delete_on_upload_succeed",
  });
  return response.json();
}

export async function listOfflineDownloadTasks(taskIds: string[]): Promise<AListTaskListResponse> {
  const response = await postJson("/api/fs/offline_download/tasks", { task_ids: taskIds });
  return response.json();
}

export async function previewRetrieval({
  kbId,
  question,
  retrievalProfile,
  token,
}: {
  kbId: number;
  question: string;
  retrievalProfile?: RetrievalProfile | null;
  token: string;
}): Promise<RetrievalPreviewResponse> {
  const response = await postJson(
    `/api/v1/kbs/${kbId}/retrieval/preview`,
    {
      question,
      search_type: retrievalProfile?.search_type,
      top_k: retrievalProfile?.top_k,
      fetch_k: retrievalProfile?.fetch_k,
      reranker_enabled: retrievalProfile?.reranker_enabled,
    },
    token,
  );
  return response.json();
}

export async function streamChat({
  kbId,
  message,
  sessionId,
  token,
  onEvent,
}: {
  kbId: number;
  message: string;
  retrievalProfile?: RetrievalProfile;
  sessionId?: number;
  token: string;
  onEvent: (event: StreamEvent) => void;
}) {
  const response = await postJson(
    `/api/v1/kbs/${kbId}/chat/stream`,
    {
      question: message,
      session_id: sessionId,
    },
    token,
  );

  const reader = response.body?.getReader();
  if (!reader) throw new Error("当前浏览器不支持流式响应");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    buffer = parseSse(buffer, onEvent);
  }
}

function parseSse(buffer: string, onEvent: (event: StreamEvent) => void) {
  const chunks = buffer.split("\n\n");
  const rest = chunks.pop() || "";

  for (const chunk of chunks) {
    let eventName = "message";
    const dataLines: string[] = [];
    for (const line of chunk.split("\n")) {
      if (line.startsWith("event:")) eventName = line.slice(6).trim();
      if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
    }
    if (!dataLines.length) continue;
    onEvent({
      eventName: eventName as StreamEvent["eventName"],
      data: JSON.parse(dataLines.join("\n")),
    } as StreamEvent);
  }

  return rest;
}
