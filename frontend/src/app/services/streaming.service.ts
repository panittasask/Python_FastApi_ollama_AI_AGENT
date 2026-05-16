import { Injectable, inject } from "@angular/core";
import { ChatAttachment, ChatMessage, ChatStreamEvent } from "../core/models";
import { SettingsService } from "./settings.service";

export interface StreamChatOptions {
  message: string;
  model: string;
  conversationId: string;
  history: ChatMessage[];
  attachments?: ChatAttachment[];
  system?: string;
  temperature?: number;
  topP?: number;
  numCtx?: number;
  maxTokens?: number;
  mode?: "auto" | "chat" | "agent";
  projectName?: string;
  outputPath?: string;
  forceProject?: boolean;
  webSearch?: boolean;
  webSearchQuery?: string;
  perAgentModels?: boolean;
  signal?: AbortSignal;
  onEvent: (ev: ChatStreamEvent) => void;
}

/**
 * Streaming chat client built on top of the Fetch API so we can read
 * Server-Sent Events incrementally and cancel mid-stream via AbortController.
 */
@Injectable({ providedIn: "root" })
export class StreamingService {
  private settings = inject(SettingsService);
  private get base(): string {
    return this.settings.apiBaseUrl();
  }

  async streamChat(opts: StreamChatOptions): Promise<void> {
    const body = {
      message: opts.message,
      model: opts.model,
      conversation_id: opts.conversationId,
      history: opts.history.map((m) => ({ role: m.role, content: m.content })),
      attachments: (opts.attachments || []).map((a) => ({
        name: a.name,
        content: a.content,
        size: a.size,
        mime: a.mime,
      })),
      system: opts.system || undefined,
      temperature: opts.temperature,
      top_p: opts.topP,
      num_ctx: opts.numCtx,
      max_tokens: opts.maxTokens,
      mode: opts.mode || "auto",
      project_name: opts.projectName,
      output_path: opts.outputPath,
      force_project: opts.forceProject,
      web_search: !!opts.webSearch,
      web_search_query: opts.webSearchQuery,
      per_agent_models: !!opts.perAgentModels,
      stream: true,
    };

    let resp: Response;
    try {
      resp = await fetch(`${this.base}/api/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify(body),
        signal: opts.signal,
      });
    } catch (e: unknown) {
      if ((e as Error).name === "AbortError") {
        opts.onEvent({ type: "cancelled" });
        return;
      }
      opts.onEvent({ type: "error", message: (e as Error).message });
      return;
    }

    if (!resp.ok || !resp.body) {
      opts.onEvent({
        type: "error",
        message: `HTTP ${resp.status} ${resp.statusText}`,
      });
      return;
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    try {
      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // SSE: events are separated by a blank line
        let idx: number;
        while ((idx = buffer.indexOf("\n\n")) !== -1) {
          const raw = buffer.slice(0, idx).trim();
          buffer = buffer.slice(idx + 2);
          if (!raw) continue;
          const dataLines = raw
            .split("\n")
            .filter((l) => l.startsWith("data:"))
            .map((l) => l.slice(5).trim());
          if (!dataLines.length) continue;
          const payload = dataLines.join("\n");
          if (payload === "[DONE]") {
            opts.onEvent({ type: "done" });
            continue;
          }
          try {
            const ev = JSON.parse(payload) as ChatStreamEvent;
            opts.onEvent(ev);
          } catch {
            opts.onEvent({ type: "chunk", content: payload });
          }
        }
      }
      opts.onEvent({ type: "done" });
    } catch (e: unknown) {
      if ((e as Error).name === "AbortError") {
        opts.onEvent({ type: "cancelled" });
        return;
      }
      opts.onEvent({ type: "error", message: (e as Error).message });
    } finally {
      try {
        reader.releaseLock();
      } catch {
        /* noop */
      }
    }
  }
}
