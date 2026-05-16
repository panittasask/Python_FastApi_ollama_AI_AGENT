export interface OllamaModel {
  name: string;
  size?: number | null;
  family?: string | null;
  modified_at?: string | null;
}

export type ChatRole = "user" | "assistant" | "system";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  createdAt: number;
  /** True while tokens are still streaming in. */
  streaming?: boolean;
  /** Whether the user stopped this message mid-stream. */
  cancelled?: boolean;
  /** Model used for this assistant response. */
  model?: string;
  /** Files attached by the user to this message. */
  attachments?: ChatAttachment[];
}

export interface ChatAttachment {
  name: string;
  /** UTF-8 text content (binary files are rejected on the client). */
  content: string;
  size: number;
  mime?: string;
  truncated?: boolean;
}

export interface Conversation {
  id: string;
  title: string;
  model: string;
  messages: ChatMessage[];
  createdAt: number;
  updatedAt: number;
}

export interface ChatSettings {
  apiBaseUrl: string;
  model: string;
  temperature: number;
  topP: number;
  maxTokens: number;
  numCtx: number;
  streaming: boolean;
  outputPath: string;
  systemPrompt: string;
}

export const DEFAULT_SETTINGS: ChatSettings = {
  apiBaseUrl: "",
  model: "",
  temperature: 0.2,
  topP: 0.9,
  maxTokens: 4096,
  numCtx: 8192,
  streaming: true,
  outputPath: "./generated_projects",
  systemPrompt: "",
};

export interface ChatStreamEvent {
  type: "start" | "chunk" | "done" | "error" | "cancelled";
  content?: string;
  conversation_id?: string;
  model?: string;
  message?: string;
}

export interface PlanFile {
  project: string;
  path?: string;
}

export interface PlanResponse {
  project: string;
  markdown: string;
}
