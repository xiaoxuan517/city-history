export type Citation = {
  rank?: number;
  source?: string;
  document_id?: number;
  filename?: string;
  chunk_id?: number;
  page?: string | null;
  chunk_index?: number | null;
  content?: string;
  score?: number;
};

export type PublicConfig = {
  chat_model: string;
  embedding_model: string;
  top_k: number;
  retrieval_search_type: string;
  retrieval_fetch_k: number;
  reranker_enabled: boolean;
  reranker_strategy: string;
  retrieval_max_context_chars: number;
};

export type User = {
  id: number;
  username: string;
  email: string;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
  user: User;
};

export type KnowledgeBase = {
  id: number;
  user_id: number;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
};

export type DocumentStatus = "pending" | "processing" | "completed" | "failed";

export type KnowledgeDocument = {
  id: number;
  kb_id: number;
  user_id: number;
  filename: string;
  content_type: string | null;
  file_path: string;
  status: DocumentStatus;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type KnowledgeBaseWithDocumentResponse = {
  knowledge_base: KnowledgeBase;
  document: KnowledgeDocument;
};

export type AssistantAction = {
  type: string;
  payload: Record<string, unknown>;
};

export type AssistantChatResponse = {
  answer: string;
  actions: AssistantAction[];
  state: Record<string, unknown>;
  session_id: number | null;
  run_id: number | null;
};

export type AssistantStreamEvent =
  | {
      eventName: "metadata";
      data: { run_id: number; session_id: number };
    }
  | {
      eventName: "answer_delta";
      data: { content?: string; answer?: string };
    }
  | {
      eventName: "tool_result";
      data: Record<string, unknown>;
    }
  | {
      eventName: "complete";
      data: AssistantChatResponse;
    }
  | {
      eventName: "end";
      data: Record<string, never>;
    }
  | {
      eventName: "error";
      data: { message?: string };
    };

export type SearchType = "similarity" | "mmr" | "hybrid";

export type RetrievalProfile = {
  search_type: SearchType;
  top_k: number;
  fetch_k: number;
  reranker_enabled: boolean;
  max_context_chars: number;
};

export type FeedbackRating = "up" | "down";

export type ToolTrace = {
  toolName?: string;
  statusLine?: string;
  content: string;
  citations?: Citation[];
};

export type ChatResponse = {
  answer: string;
  references: Citation[];
  session_id: number;
  run_id: number;
  cache_hit?: boolean;
  usage: Record<string, unknown> | null;
  token_cost?: Record<string, unknown> | null;
};

export type ChatSession = {
  id: number;
  user_id: number;
  kb_id: number | null;
  title: string | null;
  created_at: string;
  updated_at: string;
};

export type StoredChatMessage = {
  id: number;
  session_id: number;
  role: "assistant" | "user" | "system";
  content: string;
  references: Citation[];
  created_at: string;
  updated_at: string;
};

export type ChatRun = {
  id: number;
  session_id: number;
  user_id: number;
  kb_id: number | null;
  prompt_version_id: number | null;
  status: "running" | "completed" | "failed" | "cancelled";
  question: string;
  answer: string | null;
  references: Citation[];
  usage: Record<string, unknown>;
  token_cost: Record<string, unknown>;
  trace_id: string | null;
  trace_url: string | null;
  cache_hit: boolean;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type ChatRunEvent = {
  id: number;
  run_id: number;
  user_id: number;
  kb_id: number | null;
  event_type: string;
  sequence: number;
  payload: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type RetrievalPreviewChunk = {
  rank: number | null;
  document_id: number | string | null;
  filename: string;
  chunk_id: number | string | null;
  chunk_index: number | null;
  page?: string | null;
  score?: number | null;
  content: string;
  metadata: Record<string, unknown>;
};

export type RetrievalPreviewResponse = {
  question: string;
  kb_id: number;
  chunks: RetrievalPreviewChunk[];
};

export type AListFileItem = {
  id: string;
  path: string;
  name: string;
  size: number;
  is_dir: boolean;
  modified: string;
  created: string;
  sign: string;
  thumb: string;
  type: number;
  hashinfo: string;
  hash_info: {
    md5?: string | null;
  } | null;
  virtual_path?: string | null;
  label_list:
    | {
        id: number;
        type: number;
        name: string;
        create_time: string;
      }[]
    | null;
};

export type AListFileListResponse = {
  code: number;
  message: string;
  data: {
    content: AListFileItem[];
    total: number;
    readme: string;
    header: string;
    write: boolean;
    provider: string;
  };
};

export type GazetteerFile = {
  id: number;
  name: string;
  full_path: string;
  source_path: string;
  is_downloaded: boolean;
  local_download_task_id: string | null;
  size: number;
  modified: string;
  synced_at: string;
  created_at: string;
  updated_at: string;
};

export type GazetteerFileListResponse = {
  items: GazetteerFile[];
  total: number;
  page: number;
  per_page: number;
};

export type OldPicture = {
  id: number;
  name: string;
  full_path: string;
  source_path: string;
  is_downloaded: boolean;
  local_download_task_id: string | null;
  size: number;
  modified: string;
  synced_at: string;
  created_at: string;
  updated_at: string;
};

export type OldPictureListResponse = {
  items: OldPicture[];
  total: number;
  page: number;
  per_page: number;
};

export type LocalOldPicture = {
  name: string;
  preview_name: string;
  size: number;
  modified: string;
  local_download_task_id: string;
};

export type LocalOldPictureListResponse = {
  items: LocalOldPicture[];
  total: number;
  offset: number;
  limit: number;
};

export type AListTask = {
  id: string;
  name: string;
  state: number;
  status: string;
  progress: number;
  error: string;
};

export type AListOfflineDownloadResponse = {
  code: number;
  message: string;
  data: {
    tasks: AListTask[];
  };
};

export type AListTaskListResponse = {
  code: number;
  message: string;
  data: {
    tasks: AListTask[];
  };
};

export type ChatMessage = {
  id: string;
  role: "assistant" | "user";
  content: string;
  question?: string;
  statusLines?: string[];
  citations?: Citation[];
  retrievalProfile?: RetrievalProfile;
  toolTraces?: ToolTrace[];
  usage?: Record<string, unknown> | null;
  tokenCost?: Record<string, unknown> | null;
  runEvents?: ChatRunEvent[];
  runId?: number | null;
  traceUrl?: string | null;
  elapsedMs?: number | null;
  feedbackRating?: FeedbackRating;
  feedbackPending?: boolean;
  error?: boolean;
};

export type StreamEvent =
  | {
      eventName: "metadata";
      data: {
        run_id: number;
        session_id: number;
        kb_id?: number;
      };
    }
  | {
      eventName: "answer";
      data: { content?: string; answer?: string };
    }
  | {
      eventName: "answer_delta";
      data: { content?: string; answer?: string };
    }
  | {
      eventName: "tool_call" | "tool_result";
      data: {
        status_line?: string;
        tool_name?: string;
        content?: string;
        citations?: Citation[];
      };
    }
  | {
      eventName: "complete";
      data: ChatResponse;
    }
  | {
      eventName: "end";
      data: Record<string, never>;
    }
  | {
      eventName: "error";
      data: { message?: string };
    };
