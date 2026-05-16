import { Injectable, computed, effect, inject, signal } from "@angular/core";
import {
  AgentActivity,
  ChatAttachment,
  Conversation,
  ChatMessage,
  ChatStreamEvent,
  WebSearchResult,
} from "../core/models";
import { StreamingService } from "./streaming.service";
import { SettingsService } from "./settings.service";

const KEY = "agent_ui.conversations";
const MAX_CONVS = 200;

function uid(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return (crypto as Crypto).randomUUID().replace(/-/g, "").slice(0, 16);
  }
  return Math.random().toString(36).slice(2, 12) + Date.now().toString(36);
}

@Injectable({ providedIn: "root" })
export class ChatService {
  private streamer = inject(StreamingService);
  private settings = inject(SettingsService);

  private readonly _conversations = signal<Conversation[]>(this.load());
  private readonly _activeId = signal<string | null>(null);
  private readonly _streaming = signal(false);
  private readonly _agentMode = signal<boolean>(this.loadAgentMode());
  private readonly _webSearchMode = signal<boolean>(
    this.loadBool("agent_ui.webSearch"),
  );
  private readonly _perAgentModelsMode = signal<boolean>(
    this.loadBool("agent_ui.perAgentModels"),
  );
  private _abort: AbortController | null = null;

  readonly conversations = computed(() =>
    [...this._conversations()].sort((a, b) => b.updatedAt - a.updatedAt),
  );
  readonly activeId = computed(() => this._activeId());
  readonly active = computed<Conversation | null>(() => {
    const id = this._activeId();
    if (!id) return null;
    return this._conversations().find((c) => c.id === id) ?? null;
  });
  readonly streaming = computed(() => this._streaming());
  readonly agentMode = computed(() => this._agentMode());
  readonly webSearchMode = computed(() => this._webSearchMode());
  readonly perAgentModelsMode = computed(() => this._perAgentModelsMode());

  setAgentMode(on: boolean): void {
    this._agentMode.set(on);
    try {
      localStorage.setItem("agent_ui.agentMode", on ? "1" : "0");
    } catch {
      /* noop */
    }
  }
  toggleAgentMode(): void {
    this.setAgentMode(!this._agentMode());
  }
  private loadAgentMode(): boolean {
    try {
      return localStorage.getItem("agent_ui.agentMode") === "1";
    } catch {
      return false;
    }
  }

  setWebSearchMode(on: boolean): void {
    this._webSearchMode.set(on);
    try {
      localStorage.setItem("agent_ui.webSearch", on ? "1" : "0");
    } catch {
      /* noop */
    }
  }
  toggleWebSearchMode(): void {
    this.setWebSearchMode(!this._webSearchMode());
  }

  setPerAgentModelsMode(on: boolean): void {
    this._perAgentModelsMode.set(on);
    try {
      localStorage.setItem("agent_ui.perAgentModels", on ? "1" : "0");
    } catch {
      /* noop */
    }
  }
  togglePerAgentModelsMode(): void {
    this.setPerAgentModelsMode(!this._perAgentModelsMode());
  }

  private loadBool(key: string): boolean {
    try {
      return localStorage.getItem(key) === "1";
    } catch {
      return false;
    }
  }

  constructor() {
    effect(() => {
      try {
        localStorage.setItem(KEY, JSON.stringify(this._conversations()));
      } catch {
        /* noop */
      }
    });
  }

  // ---------- conversation management ----------

  newConversation(model?: string): Conversation {
    const m = model || this.settings.settings().model || "";
    const conv: Conversation = {
      id: uid(),
      title: "New chat",
      model: m,
      messages: [],
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };
    this._conversations.update((list) => [conv, ...list].slice(0, MAX_CONVS));
    this._activeId.set(conv.id);
    return conv;
  }

  select(id: string): void {
    if (this._conversations().some((c) => c.id === id)) {
      this._activeId.set(id);
    }
  }

  rename(id: string, title: string): void {
    this._conversations.update((list) =>
      list.map((c) =>
        c.id === id
          ? { ...c, title: title.trim() || c.title, updatedAt: Date.now() }
          : c,
      ),
    );
  }

  remove(id: string): void {
    this._conversations.update((list) => list.filter((c) => c.id !== id));
    if (this._activeId() === id) this._activeId.set(null);
  }

  clearAll(): void {
    this._conversations.set([]);
    this._activeId.set(null);
  }

  setModel(id: string, model: string): void {
    this._conversations.update((list) =>
      list.map((c) =>
        c.id === id ? { ...c, model, updatedAt: Date.now() } : c,
      ),
    );
  }

  // ---------- messaging ----------

  private updateConv(
    id: string,
    patch: (c: Conversation) => Conversation,
  ): void {
    this._conversations.update((list) =>
      list.map((c) => (c.id === id ? patch(c) : c)),
    );
  }

  private appendMessage(id: string, msg: ChatMessage): void {
    this.updateConv(id, (c) => ({
      ...c,
      messages: [...c.messages, msg],
      updatedAt: Date.now(),
    }));
  }

  private patchMessage(
    id: string,
    msgId: string,
    patch: Partial<ChatMessage>,
  ): void {
    this.updateConv(id, (c) => ({
      ...c,
      messages: c.messages.map((m) =>
        m.id === msgId ? { ...m, ...patch } : m,
      ),
      updatedAt: Date.now(),
    }));
  }

  /** Append text to a message efficiently (kept on a signal write). */
  private appendChunk(id: string, msgId: string, chunk: string): void {
    this.updateConv(id, (c) => ({
      ...c,
      messages: c.messages.map((m) =>
        m.id === msgId ? { ...m, content: m.content + chunk } : m,
      ),
      updatedAt: Date.now(),
    }));
  }

  /** Send a user message and stream the assistant reply. */
  async send(text: string, attachments: ChatAttachment[] = []): Promise<void> {
    const trimmed = text.trim();
    if ((!trimmed && attachments.length === 0) || this._streaming()) return;
    let conv = this.active();
    if (!conv) {
      conv = this.newConversation();
    }
    const convId = conv.id;
    const settings = this.settings.settings();
    const model = conv.model || settings.model;
    if (!model) {
      this.appendMessage(convId, {
        id: uid(),
        role: "assistant",
        content:
          "⚠️ No model selected. Pick a model in the top bar or open Settings.",
        createdAt: Date.now(),
      });
      return;
    }

    // user message
    const userMsg: ChatMessage = {
      id: uid(),
      role: "user",
      content: trimmed,
      createdAt: Date.now(),
      attachments: attachments.length ? attachments : undefined,
    };
    this.appendMessage(convId, userMsg);

    // auto-title from first user message
    if (conv.messages.length === 0 || conv.title === "New chat") {
      const titleSource = trimmed || (attachments[0]?.name ?? "New chat");
      const title =
        titleSource.slice(0, 48) + (titleSource.length > 48 ? "…" : "");
      this.updateConv(convId, (c) => ({ ...c, title, updatedAt: Date.now() }));
    }

    // assistant placeholder
    const assistantMsg: ChatMessage = {
      id: uid(),
      role: "assistant",
      content: "",
      createdAt: Date.now(),
      streaming: true,
      model,
    };
    this.appendMessage(convId, assistantMsg);

    // build history excluding the freshly added placeholder
    const history = this.active()!
      .messages.filter((m) => m.id !== assistantMsg.id)
      .map((m) => ({ ...m }));

    this._streaming.set(true);
    this._abort = new AbortController();

    await this.streamer.streamChat({
      message: userMsg.content,
      model,
      conversationId: convId,
      history: history.slice(0, -1), // exclude the user message we just sent
      attachments: userMsg.attachments,
      system: settings.systemPrompt || undefined,
      temperature: settings.temperature,
      topP: settings.topP,
      numCtx: settings.numCtx,
      maxTokens: settings.maxTokens,
      mode: this._agentMode() ? "agent" : "auto",
      outputPath: settings.outputPath || undefined,
      webSearch: this._webSearchMode(),
      perAgentModels: this._perAgentModelsMode(),
      signal: this._abort.signal,
      onEvent: (ev: ChatStreamEvent) =>
        this.handleEvent(convId, assistantMsg.id, ev),
    });

    this.patchMessage(convId, assistantMsg.id, { streaming: false });
    this._streaming.set(false);
    this._abort = null;
  }

  private handleEvent(
    convId: string,
    msgId: string,
    ev: ChatStreamEvent,
  ): void {
    switch (ev.type) {
      case "start":
        return;
      case "chunk":
        if (ev.content) this.appendChunk(convId, msgId, ev.content);
        return;
      case "agent": {
        const act: AgentActivity = {
          name: ev.name || "agent",
          model: ev.model || "",
          status: (ev.status as AgentActivity["status"]) || "start",
          message: ev.message,
          updatedAt: Date.now(),
        };
        this.updateConv(convId, (c) => ({
          ...c,
          messages: c.messages.map((m) => {
            if (m.id !== msgId) return m;
            const list = [...(m.agents || [])];
            const idx = list.findIndex(
              (a) => a.name === act.name && a.model === act.model,
            );
            if (idx >= 0) list[idx] = act;
            else list.push(act);
            return { ...m, agents: list };
          }),
          updatedAt: Date.now(),
        }));
        return;
      }
      case "web_search": {
        const results: WebSearchResult[] = ev.results || [];
        this.patchMessage(convId, msgId, { sources: results });
        return;
      }
      case "done":
        this.patchMessage(convId, msgId, { streaming: false });
        return;
      case "cancelled":
        this.patchMessage(convId, msgId, { streaming: false, cancelled: true });
        return;
      case "error":
        this.appendChunk(
          convId,
          msgId,
          `\n\n**[error]** ${ev.message ?? "unknown"}`,
        );
        this.patchMessage(convId, msgId, { streaming: false });
        return;
    }
  }

  stop(): void {
    if (this._abort) {
      this._abort.abort();
      this._abort = null;
    }
  }

  async regenerate(): Promise<void> {
    const conv = this.active();
    if (!conv || this._streaming()) return;
    const lastAssistantIdx = [...conv.messages]
      .reverse()
      .findIndex((m) => m.role === "assistant");
    if (lastAssistantIdx < 0) return;
    const realIdx = conv.messages.length - 1 - lastAssistantIdx;
    const lastUser = [...conv.messages.slice(0, realIdx)]
      .reverse()
      .find((m) => m.role === "user");
    if (!lastUser) return;
    // drop last assistant message
    this.updateConv(conv.id, (c) => ({
      ...c,
      messages: c.messages.slice(0, realIdx),
      updatedAt: Date.now(),
    }));
    await this.send(lastUser.content, lastUser.attachments ?? []);
  }

  exportConversation(id: string): string {
    const c = this._conversations().find((x) => x.id === id);
    if (!c) return "";
    return JSON.stringify(c, null, 2);
  }

  private load(): Conversation[] {
    try {
      const raw = localStorage.getItem(KEY);
      if (!raw) return [];
      const arr = JSON.parse(raw) as Conversation[];
      if (!Array.isArray(arr)) return [];
      return arr;
    } catch {
      return [];
    }
  }
}
