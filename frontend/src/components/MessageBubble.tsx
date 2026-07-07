import { ThumbsDown, ThumbsUp } from "lucide-react";

import type { ChatMessage, ChatRunEvent, Citation, FeedbackRating, ToolTrace } from "../types";

type RetrievedSnippet = {
  label: string;
  content: string;
  citation?: Citation;
};

function citationTitle(citation: Citation) {
  const filename = citation.filename || citation.source || "引用";
  const parts = [filename];
  if (citation.page) parts.push(`p.${citation.page}`);
  if (citation.chunk_index !== undefined && citation.chunk_index !== null) parts.push(`chunk ${citation.chunk_index}`);
  return parts.join(" · ");
}

function parseToolSnippets(trace: ToolTrace): RetrievedSnippet[] {
  if (!trace.content || trace.content === "No relevant context found.") return [];
  const sections = trace.content
    .split(/\n{2,}/)
    .map((section) => section.trim())
    .filter(Boolean)
    .filter((section) => !section.startsWith("Context summary:"));

  return sections
    .map((section) => {
      const [header, ...bodyParts] = section.split("\n");
      const body = bodyParts.join("\n").trim();
      const rank = Number(header.match(/^\[(\d+)\]/)?.[1]);
      const citation = Number.isFinite(rank) ? trace.citations?.find((item) => item.rank === rank) : undefined;
      return {
        label: citation ? citationTitle(citation) : header.replace(/^\[\d+\]\s*/, ""),
        content: body || section,
        citation,
      };
    })
    .filter((snippet) => snippet.content);
}

function MessageBubble({
  message,
  onFeedback,
}: {
  message: ChatMessage;
  onFeedback: (message: ChatMessage, rating: FeedbackRating) => void;
}) {
  const totalTokens = message.usage?.total_tokens;
  const totalCost = message.tokenCost?.total_cost;
  const currency = typeof message.tokenCost?.currency === "string" ? message.tokenCost.currency : "USD";
  const profile = message.retrievalProfile;
  const canSendFeedback =
    message.role === "assistant" && message.id !== "welcome" && !message.error && message.elapsedMs !== undefined;
  return (
    <article className={`message ${message.role}`}>
      <div className="avatar" aria-hidden="true">
        {message.role === "user" ? "你" : "AI"}
      </div>
      <div className={`bubble ${message.error ? "error" : ""}`}>
        <p>{message.content}</p>
        {!!message.statusLines?.length && <div className="status-lines">{message.statusLines.join(" | ")}</div>}
        {profile && (
          <div className="profile-snapshot">
            <span>{profile.search_type}</span>
            <span>top={profile.top_k}</span>
            <span>fetch={profile.fetch_k}</span>
            <span>rerank={profile.reranker_enabled ? "on" : "off"}</span>
            <span>ctx={profile.max_context_chars}</span>
          </div>
        )}
        {!!message.citations?.length && (
          <div className="reference-panel">
            <div className="reference-title">引用片段</div>
            <div className="citations">
              {message.citations.map((citation, index) => (
                <span
                  className="citation"
                  key={`${citation.chunk_id || citation.filename || citation.source || "ref"}-${index}`}
                >
                  {citationTitle(citation)}
                </span>
              ))}
            </div>
            {message.citations.some((citation) => citation.content) && (
              <div className="retrieved-snippets compact">
                {message.citations
                  .filter((citation) => citation.content)
                  .map((citation, index) => (
                    <div className="retrieved-snippet" key={`${citationTitle(citation)}-${index}`}>
                      <div className="snippet-label">{citationTitle(citation)}</div>
                      <p>{citation.content}</p>
                    </div>
                  ))}
              </div>
            )}
          </div>
        )}
        {!!message.toolTraces?.length && (
          <div className="tool-traces">
            {message.toolTraces.map((trace, index) => (
              <details className="tool-trace" key={`${trace.toolName || "tool"}-${index}`}>
                <summary>
                  <span>{trace.statusLine || trace.toolName || "tool_result"}</span>
                  {!!trace.citations?.length && <small>{trace.citations.length} 个片段</small>}
                </summary>
                <SnippetList trace={trace} />
                <pre>{trace.content}</pre>
              </details>
            ))}
          </div>
        )}
        {!!message.runEvents?.length && (
          <details className="run-timeline">
            <summary>
              <span>执行 Trace</span>
              <small>{message.runEvents.length} 个事件</small>
            </summary>
            <div className="run-events">
              {message.runEvents.map((event) => (
                <RunEventItem event={event} key={event.id} />
              ))}
            </div>
          </details>
        )}
        {(message.elapsedMs !== undefined ||
          totalTokens !== undefined ||
          totalCost !== undefined ||
          message.traceUrl) && (
          <div className="usage">
            {message.elapsedMs !== undefined && message.elapsedMs !== null ? `${message.elapsedMs} ms` : ""}
            {message.elapsedMs !== undefined && totalTokens !== undefined ? " | " : ""}
            {totalTokens !== undefined ? `tokens=${String(totalTokens)}` : ""}
            {(totalTokens !== undefined || message.elapsedMs !== undefined) && totalCost !== undefined ? " | " : ""}
            {totalCost !== undefined ? `cost=${String(totalCost)} ${currency}` : ""}
            {(totalTokens !== undefined || totalCost !== undefined || message.elapsedMs !== undefined) &&
            message.traceUrl
              ? " | "
              : ""}
            {message.traceUrl && (
              <a href={message.traceUrl} rel="noreferrer" target="_blank">
                trace
              </a>
            )}
          </div>
        )}
        {canSendFeedback && (
          <div className="feedback-actions" aria-label="回答反馈">
            <button
              className={message.feedbackRating === "up" ? "selected" : ""}
              disabled={message.feedbackPending}
              onClick={() => onFeedback(message, "up")}
              title="有帮助"
              type="button"
            >
              <ThumbsUp size={15} />
            </button>
            <button
              className={message.feedbackRating === "down" ? "selected" : ""}
              disabled={message.feedbackPending}
              onClick={() => onFeedback(message, "down")}
              title="没帮助"
              type="button"
            >
              <ThumbsDown size={15} />
            </button>
          </div>
        )}
      </div>
    </article>
  );
}

function RunEventItem({ event }: { event: ChatRunEvent }) {
  const toolName = typeof event.payload.tool_name === "string" ? event.payload.tool_name : "";
  const statusLine = typeof event.payload.status_line === "string" ? event.payload.status_line : "";
  const referenceCount =
    typeof event.payload.reference_count === "number"
      ? event.payload.reference_count
      : Array.isArray(event.payload.citations)
        ? event.payload.citations.length
        : undefined;
  const totalTokens =
    typeof event.payload.usage === "object" &&
    event.payload.usage !== null &&
    "total_tokens" in event.payload.usage
      ? String((event.payload.usage as Record<string, unknown>).total_tokens)
      : "";

  return (
    <div className="run-event">
      <div className="run-event-head">
        <strong>
          #{event.sequence} {event.event_type}
        </strong>
        {toolName && <span>{toolName}</span>}
      </div>
      {statusLine && <p>{statusLine}</p>}
      <div className="run-event-meta">
        {referenceCount !== undefined && <span>refs={referenceCount}</span>}
        {totalTokens && <span>tokens={totalTokens}</span>}
      </div>
    </div>
  );
}

function SnippetList({ trace }: { trace: ToolTrace }) {
  const snippets = parseToolSnippets(trace);
  if (!snippets.length) return <div className="snippet-empty">没有命中可用片段</div>;

  return (
    <div className="retrieved-snippets">
      {snippets.map((snippet, index) => (
        <div className="retrieved-snippet" key={`${snippet.label}-${index}`}>
          <div className="snippet-label">{snippet.label}</div>
          <p>{snippet.content}</p>
        </div>
      ))}
    </div>
  );
}

export default MessageBubble;
