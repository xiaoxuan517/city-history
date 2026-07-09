import { FormEvent, useEffect, useRef, useState } from "react";

import {
  cancelChatRun,
  checkHealth,
  createKnowledgeBase,
  createKnowledgeBaseFromDownload,
  deleteDocument,
  deleteChatSession,
  deleteKnowledgeBase,
  getChatRun,
  isUnauthorizedApiError,
  listChatRunEvents,
  listDocuments,
  listChatMessages,
  listChatSessions,
  listKnowledgeBases,
  loadConfig,
  loadMe,
  processDocument,
  previewRetrieval,
  streamChat,
  updateKnowledgeBase,
  uploadDocument,
} from "./api";
import AssistantPage from "./components/AssistantPage";
import AuthPanel from "./components/AuthPanel";
import ChatPanel from "./components/ChatPanel";
import DocumentPanel from "./components/DocumentPanel";
import GazetteerPage from "./components/GazetteerPage";
import HistoryAlbumPage from "./components/HistoryAlbumPage";
import HomePage from "./components/HomePage";
import KbManager from "./components/KbManager";
import KnowledgeBaseListPage from "./components/KnowledgeBaseListPage";
import Sidebar from "./components/Sidebar";
import SiteNav from "./components/SiteNav";
import type {
  ChatMessage,
  ChatSession,
  Citation,
  FeedbackRating,
  KnowledgeDocument,
  KnowledgeBase,
  PublicConfig,
  RetrievalProfile,
  StreamEvent,
  TokenResponse,
  ToolTrace,
  User,
} from "./types";

const welcomeMessage: ChatMessage = {
  id: "welcome",
  role: "assistant",
  content: "你好，我可以基于当前县志知识库回答问题，并尽量返回可核验的来源片段。",
};

const tokenStorageKey = "rag_access_token";
const userStorageKey = "rag_current_user";
const authNoticeStorageKey = "rag_auth_notice";
type AppView = "home" | "auth" | "kbList" | "workspace" | "gazetteers" | "assistant" | "historyAlbum";

function pathToView(pathname: string): AppView {
  if (pathname.startsWith("/login")) return "auth";
  if (pathname.startsWith("/assistant")) return "assistant";
  if (pathname.startsWith("/history-album")) return "historyAlbum";
  if (/^\/workspace\/\d+/.test(pathname)) return "workspace";
  if (pathname.startsWith("/workspace")) return "kbList";
  if (pathname.startsWith("/gazetteers")) return "gazetteers";
  return "home";
}

function pathToKbId(pathname: string) {
  const match = pathname.match(/^\/workspace\/(\d+)/);
  return match ? Number(match[1]) : null;
}

function knowledgeBaseNameFromFilename(filename: string) {
  const name = filename.replace(/\.[^.]+$/, "").trim() || filename.trim() || "县志知识库";
  return name.length > 128 ? name.slice(0, 128) : name;
}

function loadStoredUser() {
  const rawUser = localStorage.getItem(userStorageKey);
  if (!rawUser) return null;
  try {
    return JSON.parse(rawUser) as User;
  } catch {
    localStorage.removeItem(userStorageKey);
    return null;
  }
}

function loadAuthNotice() {
  const notice = sessionStorage.getItem(authNoticeStorageKey) || "";
  if (notice) sessionStorage.removeItem(authNoticeStorageKey);
  return notice;
}

function App() {
  const [apiToken, setApiToken] = useState(() => localStorage.getItem(tokenStorageKey) || "");
  const [view, setView] = useState<AppView>(() => pathToView(window.location.pathname));
  const [currentUser, setCurrentUser] = useState<User | null>(() => loadStoredUser());
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([]);
  const [activeKbId, setActiveKbId] = useState<number | null>(null);
  const [sessionId, setSessionId] = useState<number | undefined>(undefined);
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [defaultRetrievalProfile, setDefaultRetrievalProfile] = useState<RetrievalProfile | null>(null);
  const [retrievalProfile, setRetrievalProfile] = useState<RetrievalProfile | null>(null);
  const [apiStatus, setApiStatus] = useState("连接中");
  const [workspaceError, setWorkspaceError] = useState("");
  const [authNotice, setAuthNotice] = useState(() => loadAuthNotice());
  const [workspacePending, setWorkspacePending] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([welcomeMessage]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [activeRunId, setActiveRunId] = useState<number | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    void boot();
  }, []);

  useEffect(() => {
    function syncViewFromLocation() {
      setView(pathToView(window.location.pathname));
    }

    window.addEventListener("popstate", syncViewFromLocation);
    return () => window.removeEventListener("popstate", syncViewFromLocation);
  }, []);

  useEffect(() => {
    function handleAuthExpired() {
      expireLogin();
    }

    window.addEventListener("rag:auth-expired", handleAuthExpired);
    return () => window.removeEventListener("rag:auth-expired", handleAuthExpired);
  }, []);

  useEffect(() => {
    if (!apiToken) {
      return;
    }
    void loadWorkspace(apiToken);
  }, [apiToken]);

  useEffect(() => {
    if (apiToken && currentUser && view === "auth") {
      navigateTo("kbList");
    }
  }, [apiToken, currentUser, view]);

  useEffect(() => {
    if ((view === "kbList" || view === "workspace" || view === "assistant") && !apiToken) {
      navigateTo("auth");
    }
  }, [apiToken, view]);

  useEffect(() => {
    if (!apiToken || !activeKbId) {
      setDocuments([]);
      setChatSessions([]);
      return;
    }
    void refreshDocuments();
    void refreshChatSessions();
  }, [apiToken, activeKbId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  async function boot() {
    try {
      const [newConfig, healthy] = await Promise.all([loadConfig(), checkHealth()]);
      const defaultProfile = configToProfile(newConfig);
      setConfig(newConfig);
      setDefaultRetrievalProfile(defaultProfile);
      setRetrievalProfile(defaultProfile);
      setApiStatus(healthy ? "可用" : "异常");
    } catch {
      setApiStatus("异常");
    }
  }

  async function loadWorkspace(token: string) {
    setWorkspacePending(true);
    setWorkspaceError("");
    try {
      const [user, kbs] = await Promise.all([loadMe(token), listKnowledgeBases(token)]);
      const pathKbId = pathToKbId(window.location.pathname);
      setCurrentUser(user);
      localStorage.setItem(userStorageKey, JSON.stringify(user));
      setKnowledgeBases(kbs);
      setActiveKbId((current) =>
        pathKbId && kbs.some((kb) => kb.id === pathKbId)
          ? pathKbId
          : current && kbs.some((kb) => kb.id === current)
            ? current
            : kbs[0]?.id || null,
      );
    } catch (error) {
      localStorage.removeItem(tokenStorageKey);
      localStorage.removeItem(userStorageKey);
      setApiToken("");
      setCurrentUser(null);
      setKnowledgeBases([]);
      setDocuments([]);
      setChatSessions([]);
      setActiveKbId(null);
      setWorkspaceError(error instanceof Error ? error.message : "加载用户信息失败");
    } finally {
      setWorkspacePending(false);
    }
  }

  function handleAuthenticated(tokenResponse: TokenResponse) {
    localStorage.setItem(tokenStorageKey, tokenResponse.access_token);
    localStorage.setItem(userStorageKey, JSON.stringify(tokenResponse.user));
    sessionStorage.removeItem(authNoticeStorageKey);
    setAuthNotice("");
    setApiToken(tokenResponse.access_token);
    setCurrentUser(tokenResponse.user);
    navigateTo("kbList");
  }

  function logout() {
    localStorage.removeItem(tokenStorageKey);
    localStorage.removeItem(userStorageKey);
    setApiToken("");
    setCurrentUser(null);
    setKnowledgeBases([]);
    setDocuments([]);
    setChatSessions([]);
    setActiveKbId(null);
    setSessionId(undefined);
    setMessages([welcomeMessage]);
    navigateTo("home");
  }

  function expireLogin() {
    localStorage.removeItem(tokenStorageKey);
    localStorage.removeItem(userStorageKey);
    sessionStorage.setItem(authNoticeStorageKey, "登录已过期，请重新登录。");
    setApiToken("");
    setCurrentUser(null);
    setKnowledgeBases([]);
    setDocuments([]);
    setChatSessions([]);
    setActiveKbId(null);
    setSessionId(undefined);
    setPending(false);
    setWorkspacePending(false);
    setActiveRunId(null);
    setAuthNotice("登录已过期，请重新登录。");
    setMessages([welcomeMessage]);
    navigateTo("auth");
  }

  function navigateTo(nextView: AppView) {
    const nextPath =
      nextView === "auth"
        ? "/login"
        : nextView === "kbList"
          ? "/workspace"
          : nextView === "workspace"
            ? activeKbId
              ? `/workspace/${activeKbId}`
              : "/workspace"
          : nextView === "gazetteers"
            ? "/gazetteers"
            : nextView === "assistant"
              ? "/assistant"
              : nextView === "historyAlbum"
                ? "/history-album"
                : "/";
    if (window.location.pathname !== nextPath) {
      window.history.pushState(null, "", nextPath);
    }
    setView(nextView);
  }

  function openKnowledgeBase(kbId: number) {
    setActiveKbId(kbId);
    setSessionId(undefined);
    setMessages([welcomeMessage]);
    const nextPath = `/workspace/${kbId}`;
    if (window.location.pathname !== nextPath) {
      window.history.pushState(null, "", nextPath);
    }
    setView("workspace");
  }

  async function resetThread() {
    setPending(true);
    setActiveRunId(null);
    try {
      setSessionId(undefined);
      setMessages([welcomeMessage]);
    } finally {
      setPending(false);
    }
  }

  async function createDefaultKb() {
    if (!apiToken || workspacePending) return;
    setWorkspacePending(true);
    setWorkspaceError("");
    try {
      const kb = await createKnowledgeBase(apiToken, {
        name: "默认知识库",
        description: "用于上传文档并开始问答",
      });
      setKnowledgeBases((current) => [kb, ...current]);
      setActiveKbId(kb.id);
      setSessionId(undefined);
      setChatSessions([]);
      setMessages([welcomeMessage]);
      if (window.location.pathname !== `/workspace/${kb.id}`) {
        window.history.pushState(null, "", `/workspace/${kb.id}`);
      }
      setView("workspace");
    } catch (error) {
      setWorkspaceError(error instanceof Error ? error.message : "创建知识库失败");
    } finally {
      setWorkspacePending(false);
    }
  }

  async function createKb(payload: { name: string; description?: string }) {
    if (!apiToken) return;
    const kb = await createKnowledgeBase(apiToken, payload);
    setKnowledgeBases((current) => [kb, ...current]);
    setActiveKbId(kb.id);
    setSessionId(undefined);
    setChatSessions([]);
    setMessages([welcomeMessage]);
    if (window.location.pathname !== `/workspace/${kb.id}`) {
      window.history.pushState(null, "", `/workspace/${kb.id}`);
    }
    setView("workspace");
  }

  async function updateKb(kb: KnowledgeBase, payload: { name: string; description?: string }) {
    if (!apiToken) return;
    const updated = await updateKnowledgeBase(apiToken, kb.id, payload);
    setKnowledgeBases((current) => current.map((item) => (item.id === updated.id ? updated : item)));
  }

  async function deleteKb(kb: KnowledgeBase) {
    if (!apiToken) return;
    if (kb.name === "默认知识库") return;
    await deleteKnowledgeBase(apiToken, kb.id);
    const nextKnowledgeBases = knowledgeBases.filter((item) => item.id !== kb.id);
    const nextActiveKbId = nextKnowledgeBases[0]?.id || null;
    setKnowledgeBases(nextKnowledgeBases);
    setActiveKbId(nextActiveKbId);
    setDocuments([]);
    setChatSessions([]);
    setSessionId(undefined);
    setMessages([welcomeMessage]);
    if (nextActiveKbId) {
      openKnowledgeBase(nextActiveKbId);
    } else {
      navigateTo("kbList");
    }
  }

  async function refreshDocuments() {
    if (!apiToken || !activeKbId) return;
    setWorkspaceError("");
    try {
      setDocuments(await listDocuments(apiToken, activeKbId));
    } catch (error) {
      setWorkspaceError(error instanceof Error ? error.message : "加载文档失败");
    }
  }

  async function refreshChatSessions() {
    if (!apiToken || !activeKbId) return;
    try {
      const sessions = await listChatSessions(apiToken);
      setChatSessions(sessions.filter((item) => item.kb_id === activeKbId));
    } catch (error) {
      setWorkspaceError(error instanceof Error ? error.message : "加载会话失败");
    }
  }

  async function loadSessionMessages(targetSession: ChatSession) {
    if (!apiToken || pending) return;
    setWorkspacePending(true);
    setWorkspaceError("");
    try {
      const storedMessages = await listChatMessages(apiToken, targetSession.id);
      setSessionId(targetSession.id);
      setMessages(storedMessages.length ? storedMessages.map(toChatMessage) : [welcomeMessage]);
    } catch (error) {
      setWorkspaceError(error instanceof Error ? error.message : "加载会话消息失败");
    } finally {
      setWorkspacePending(false);
    }
  }

  async function deleteActiveChatSession(targetSession: ChatSession) {
    if (!apiToken || workspacePending) return;
    const confirmed = window.confirm(`确认删除会话“${targetSession.title || `会话 ${targetSession.id}`}”？`);
    if (!confirmed) return;
    setWorkspacePending(true);
    setWorkspaceError("");
    try {
      await deleteChatSession(apiToken, targetSession.id);
      setChatSessions((current) => current.filter((item) => item.id !== targetSession.id));
      if (sessionId === targetSession.id) {
        setSessionId(undefined);
        setMessages([welcomeMessage]);
      }
    } catch (error) {
      setWorkspaceError(error instanceof Error ? error.message : "删除会话失败");
    } finally {
      setWorkspacePending(false);
    }
  }

  async function uploadActiveDocument(file: File) {
    if (!apiToken || !activeKbId) return;
    setWorkspacePending(true);
    try {
      const document = await uploadDocument(apiToken, activeKbId, file);
      setDocuments((current) => [document, ...current]);
    } finally {
      setWorkspacePending(false);
    }
  }

  async function createKbFromDownload(taskId: string, filename: string) {
    if (!apiToken || !currentUser) {
      navigateTo("auth");
      return undefined;
    }
    const knowledgeBaseName = knowledgeBaseNameFromFilename(filename);
    const existingKnowledgeBase = knowledgeBases.find((kb) => kb.name === knowledgeBaseName);
    if (existingKnowledgeBase) return existingKnowledgeBase;

    setWorkspacePending(true);
    setWorkspaceError("");
    try {
      const response = await createKnowledgeBaseFromDownload(apiToken, {
        task_id: taskId,
        name: knowledgeBaseName,
        description: `由县志文件 ${filename} 创建`,
      });
      setKnowledgeBases((current) => [response.knowledge_base, ...current]);
      setDocuments([response.document]);
      return response.knowledge_base;
    } catch (error) {
      setWorkspaceError(error instanceof Error ? error.message : "从县志文件创建知识库失败");
      throw error;
    } finally {
      setWorkspacePending(false);
    }
  }

  async function processActiveDocument(document: KnowledgeDocument) {
    if (!apiToken) return;
    setWorkspacePending(true);
    try {
      const response = await processDocument(apiToken, document.id);
      setDocuments((current) => current.map((item) => (item.id === document.id ? response.document : item)));
    } finally {
      setWorkspacePending(false);
    }
  }

  async function deleteActiveDocument(document: KnowledgeDocument) {
    if (!apiToken) return;
    setWorkspacePending(true);
    try {
      await deleteDocument(apiToken, document.id);
      setDocuments((current) => current.filter((item) => item.id !== document.id));
    } finally {
      setWorkspacePending(false);
    }
  }

  function clearMessages() {
    setMessages([welcomeMessage]);
  }

  async function submitMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = input.trim();
    if (!text || pending) return;
    if (!apiToken || !activeKbId) {
      setMessages((current) => [
        ...current,
        { id: crypto.randomUUID(), role: "user", content: text },
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "请先登录并创建或选择一个知识库。",
          error: true,
        },
      ]);
      setInput("");
      return;
    }

    const assistantId = crypto.randomUUID();
    const activeProfile = retrievalProfile ? { ...retrievalProfile } : undefined;
    setInput("");
    setPending(true);
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "user", content: text },
      { id: assistantId, role: "assistant", content: "正在生成...", question: text, retrievalProfile: activeProfile },
    ]);

    const statusLines: string[] = [];
    const citations: Citation[] = [];
    const toolTraces: ToolTrace[] = [];
    let answer = "";
    let failed = false;
    let completedRunId: number | null = null;

    try {
      await streamChat({
        kbId: activeKbId,
        message: text,
        retrievalProfile: activeProfile,
        sessionId,
        token: apiToken,
        onEvent: (eventData) => {
          handleStreamEvent(eventData, assistantId, statusLines, citations, toolTraces, (nextAnswer) => {
            answer = nextAnswer;
          }, (runId) => {
            completedRunId = runId;
          });
        },
      });
      if (completedRunId !== null) {
        await enrichAssistantWithRun(assistantId, completedRunId);
      }
      await refreshChatSessions();
    } catch (error) {
      failed = true;
      updateAssistant(assistantId, {
        content: isUnauthorizedApiError(error)
          ? "登录已过期，请重新登录。"
          : `请求失败：${error instanceof Error ? error.message : "未知错误"}`,
        error: true,
      });
    } finally {
      if (!answer && !failed) {
        updateAssistant(assistantId, { content: "没有收到回答。" });
      }
      setPending(false);
      setActiveRunId(null);
    }
  }

  async function previewActiveRetrieval() {
    const text = input.trim();
    if (!text || pending) return;
    if (!apiToken || !activeKbId) {
      setMessages((current) => [
        ...current,
        { id: crypto.randomUUID(), role: "user", content: text },
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "请先登录并创建或选择一个知识库。",
          error: true,
        },
      ]);
      return;
    }

    setPending(true);
    setInput("");
    setMessages((current) => [...current, { id: crypto.randomUUID(), role: "user", content: text }]);
    try {
      const result = await previewRetrieval({
        kbId: activeKbId,
        question: text,
        retrievalProfile,
        token: apiToken,
      });
      const citations: Citation[] = result.chunks.map((chunk) => ({
        rank: chunk.rank || undefined,
        document_id: typeof chunk.document_id === "number" ? chunk.document_id : undefined,
        filename: chunk.filename,
        chunk_id: typeof chunk.chunk_id === "number" ? chunk.chunk_id : undefined,
        chunk_index: chunk.chunk_index,
        page: chunk.page,
        score: chunk.score || undefined,
        content: chunk.content,
      }));
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: result.chunks.length
            ? `检索命中 ${result.chunks.length} 个片段，未调用 AI。`
            : "没有检索到相关片段，未调用 AI。",
          citations,
          retrievalProfile: retrievalProfile ? { ...retrievalProfile } : undefined,
        },
      ]);
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: `检索失败：${error instanceof Error ? error.message : "未知错误"}`,
          error: true,
        },
      ]);
    } finally {
      setPending(false);
    }
  }

  function handleStreamEvent(
    eventData: StreamEvent,
    assistantId: string,
    statusLines: string[],
    citations: Citation[],
    toolTraces: ToolTrace[],
    setAnswer: (answer: string) => void,
    setCompletedRunId: (runId: number) => void,
  ) {
    if (eventData.eventName === "metadata") {
      setSessionId(eventData.data.session_id);
      setActiveRunId(eventData.data.run_id);
      updateAssistant(assistantId, { runId: eventData.data.run_id });
      return;
    }

    if (eventData.eventName === "answer" || eventData.eventName === "answer_delta") {
      const answer = eventData.data.answer || eventData.data.content || "";
      setAnswer(answer);
      updateAssistant(assistantId, { content: answer || "正在生成..." });
      return;
    }

    if (eventData.eventName === "tool_call" || eventData.eventName === "tool_result") {
      if (eventData.data.status_line) statusLines.push(eventData.data.status_line);
      if (eventData.data.citations?.length) citations.push(...eventData.data.citations);
      if (eventData.eventName === "tool_result" && eventData.data.content) {
        toolTraces.push({
          toolName: eventData.data.tool_name,
          statusLine: eventData.data.status_line,
          content: eventData.data.content,
          citations: eventData.data.citations || [],
        });
      }
      updateAssistant(assistantId, {
        statusLines: [...statusLines],
        citations: [...citations],
        toolTraces: [...toolTraces],
      });
      return;
    }

    if (eventData.eventName === "complete") {
      setSessionId(eventData.data.session_id);
      setAnswer(eventData.data.answer);
      setCompletedRunId(eventData.data.run_id);
      updateAssistant(assistantId, {
        content: eventData.data.answer,
        runId: eventData.data.run_id,
        citations: eventData.data.references,
        toolTraces: [...toolTraces],
        usage: eventData.data.usage,
        tokenCost: eventData.data.token_cost,
      });
      return;
    }

    if (eventData.eventName === "error") {
      throw new Error(eventData.data.message || "请求失败");
    }
  }

  function updateAssistant(id: string, patch: Partial<ChatMessage>) {
    setMessages((current) =>
      current.map((message) => (message.id === id ? { ...message, ...patch } : message)),
    );
  }

  async function enrichAssistantWithRun(assistantId: string, runId: number) {
    if (!apiToken) return;
    try {
      const run = await getChatRun(apiToken, runId);
      const runEvents = await listChatRunEvents(apiToken, runId);
      updateAssistant(assistantId, {
        usage: run.usage,
        tokenCost: run.token_cost,
        runEvents,
        traceUrl: run.trace_url,
      });
    } catch {
      // Run enrichment is helpful but not required for the chat answer itself.
    }
  }

  async function handleFeedback(message: ChatMessage, rating: FeedbackRating) {
    if (message.feedbackPending || message.role !== "assistant" || message.id === "welcome") return;

    updateAssistant(message.id, { feedbackRating: rating, feedbackPending: false });
  }

  async function cancelActiveRun() {
    if (!apiToken || activeRunId === null) return;
    const runId = activeRunId;
    setPending(false);
    setActiveRunId(null);
    setMessages((current) =>
      current.map((message) =>
        message.runId === runId
          ? {
              ...message,
              content: message.content && message.content !== "正在生成..." ? message.content : "已请求取消当前回答。",
              statusLines: [...(message.statusLines || []), "已请求取消 run"],
            }
          : message,
      ),
    );
    try {
      await cancelChatRun(apiToken, runId);
    } catch (error) {
      setWorkspaceError(error instanceof Error ? error.message : "取消 run 失败");
    }
  }

  const activeKb = knowledgeBases.find((kb) => kb.id === activeKbId) || null;

  if (view === "home") {
    return (
      <HomePage
        apiStatus={apiStatus}
        isAuthenticated={Boolean(apiToken && currentUser)}
        username={currentUser?.username}
        onEnterLibrary={() => navigateTo("gazetteers")}
        onEnterKnowledgeBase={() => navigateTo("kbList")}
        onEnterAssistant={() => navigateTo("assistant")}
        onEnterHistoryAlbum={() => navigateTo("historyAlbum")}
        onLogin={() => navigateTo("auth")}
        onLogout={logout}
      />
    );
  }

  if (view === "gazetteers") {
    return (
      <GazetteerPage
        apiStatus={apiStatus}
        isAuthenticated={Boolean(apiToken && currentUser)}
        username={currentUser?.username}
        onHome={() => navigateTo("home")}
        onAssistant={() => navigateTo("assistant")}
        onHistoryAlbum={() => navigateTo("historyAlbum")}
        onCreateKnowledgeBaseFromDownload={createKbFromDownload}
        onKnowledgeBase={() => navigateTo("kbList")}
        onLogin={() => navigateTo("auth")}
        onLogout={logout}
        onOpenKnowledgeBase={openKnowledgeBase}
      />
    );
  }

  if (view === "historyAlbum") {
    return (
      <HistoryAlbumPage
        apiStatus={apiStatus}
        isAuthenticated={Boolean(apiToken && currentUser)}
        username={currentUser?.username}
        onHome={() => navigateTo("home")}
        onGazetteers={() => navigateTo("gazetteers")}
        onKnowledgeBase={() => navigateTo("kbList")}
        onAssistant={() => navigateTo("assistant")}
        onLogin={() => navigateTo("auth")}
        onLogout={logout}
      />
    );
  }

  if (view === "assistant" && apiToken && currentUser) {
    return (
      <AssistantPage
        apiStatus={apiStatus}
        apiToken={apiToken}
        isAuthenticated={Boolean(apiToken && currentUser)}
        username={currentUser?.username}
        onHome={() => navigateTo("home")}
        onGazetteers={() => navigateTo("gazetteers")}
        onKnowledgeBase={() => navigateTo("kbList")}
        onHistoryAlbum={() => navigateTo("historyAlbum")}
        onLogin={() => navigateTo("auth")}
        onLogout={logout}
        onOpenKnowledgeBase={openKnowledgeBase}
      />
    );
  }

  if (view === "auth" || ((view === "workspace" || view === "assistant") && (!apiToken || !currentUser))) {
    return <AuthPanel apiStatus={apiStatus} notice={authNotice} onAuthenticated={handleAuthenticated} />;
  }

  if (view === "kbList") {
    return (
      <KnowledgeBaseListPage
        apiStatus={apiStatus}
        isAuthenticated={Boolean(apiToken && currentUser)}
        username={currentUser?.username}
        knowledgeBases={knowledgeBases}
        pending={workspacePending}
        onCreateFromGazetteer={() => navigateTo("gazetteers")}
        onAssistant={() => navigateTo("assistant")}
        onHistoryAlbum={() => navigateTo("historyAlbum")}
        onHome={() => navigateTo("home")}
        onLibrary={() => navigateTo("gazetteers")}
        onLogin={() => navigateTo("auth")}
        onLogout={logout}
        onDeleteKnowledgeBase={deleteKb}
        onOpenKnowledgeBase={openKnowledgeBase}
      />
    );
  }

  return (
    <main className="heritage-home workspace-page">
      <SiteNav
        active="knowledgeBase"
        isAuthenticated={Boolean(apiToken && currentUser)}
        username={currentUser?.username}
        onHome={() => navigateTo("home")}
        onGazetteers={() => navigateTo("gazetteers")}
        onKnowledgeBase={() => navigateTo("kbList")}
        onAssistant={() => navigateTo("assistant")}
        onHistoryAlbum={() => navigateTo("historyAlbum")}
        onLogin={() => navigateTo("auth")}
        onLogout={logout}
      />

      <section className="app-shell">
        <Sidebar
          apiStatus={apiStatus}
          activeKbId={activeKbId}
          config={config}
          defaultRetrievalProfile={defaultRetrievalProfile}
          knowledgeBases={knowledgeBases}
          pending={pending}
          retrievalProfile={retrievalProfile}
          threadId={sessionId ? String(sessionId) : "-"}
          user={currentUser!}
          workspaceError={workspaceError}
          workspacePending={workspacePending}
          onCreateKb={createDefaultKb}
          onLogout={logout}
          onKbChange={openKnowledgeBase}
          onRetrievalProfileChange={setRetrievalProfile}
          onResetThread={resetThread}
          chatSessions={chatSessions}
          onSessionDelete={deleteActiveChatSession}
          onSessionSelect={loadSessionMessages}
        />
        <ChatPanel
          header={
            <>
              <KbManager
                activeKb={activeKb}
                pending={workspacePending}
                onCreate={createKb}
                onDelete={deleteKb}
                onUpdate={updateKb}
              />
              {activeKb && (
                <DocumentPanel
                  documents={documents}
                  pending={workspacePending}
                  onDelete={deleteActiveDocument}
                  onProcess={processActiveDocument}
                  onRefresh={refreshDocuments}
                  onUpload={uploadActiveDocument}
                />
              )}
            </>
          }
          input={input}
          messages={messages}
          messagesEndRef={messagesEndRef}
          pending={pending}
          activeRunId={activeRunId}
          onClear={clearMessages}
          onCancelRun={cancelActiveRun}
          onFeedback={handleFeedback}
          onInputChange={setInput}
          onPreviewRetrieval={previewActiveRetrieval}
          onSubmit={submitMessage}
        />
      </section>
    </main>
  );
}

function configToProfile(config: PublicConfig): RetrievalProfile {
  return {
    search_type: config.retrieval_search_type as RetrievalProfile["search_type"],
    top_k: config.top_k,
    fetch_k: config.retrieval_fetch_k,
    reranker_enabled: config.reranker_enabled,
    max_context_chars: config.retrieval_max_context_chars,
  };
}

function toChatMessage(message: {
  id: number;
  role: "assistant" | "user" | "system";
  content: string;
  references: Citation[];
}): ChatMessage {
  return {
    id: `stored-${message.id}`,
    role: message.role === "assistant" ? "assistant" : "user",
    content: message.content,
    citations: message.references,
  };
}

export default App;
