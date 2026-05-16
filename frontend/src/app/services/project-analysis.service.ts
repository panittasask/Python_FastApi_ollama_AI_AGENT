import { Injectable, inject } from "@angular/core";
import { HttpClient } from "@angular/common/http";
import { firstValueFrom } from "rxjs";
import { SettingsService } from "./settings.service";

export interface AnalyzeProgressEvent {
  type: "start" | "progress" | "done" | "error" | "cancelled";
  message?: string;
  path?: string;
  memory_dir?: string;
  memory?: ProjectMemory;
  markdown?: Record<string, string>;
}

export interface ProjectMemory {
  root: string;
  name: string;
  updated_at: string;
  scan: ProjectScan;
  analysis: ProjectAnalysis;
  history?: unknown[];
}

export interface ProjectScan {
  root: string;
  name: string;
  total_files: number;
  total_dirs: number;
  total_bytes: number;
  total_lines: number;
  languages: Record<string, number>;
  language_lines: Record<string, number>;
  frameworks: string[];
  package_managers: string[];
  entry_points: string[];
  config_files: string[];
  dependencies: Record<string, string[]>;
  todo_comments: { tag: string; text: string; line: string; path: string }[];
  largest_files: {
    path: string;
    size: number;
    lines: number;
    language?: string;
  }[];
  tree: string;
  sample_files: {
    path: string;
    language: string;
    content: string;
    truncated: boolean;
  }[];
  readme_excerpt?: string;
  notes: string[];
}

export interface ProjectAnalysis {
  overview: string;
  architecture: string;
  patterns: string[];
  modules: { name: string; purpose: string; files?: string[] }[];
  todos: {
    priority: string;
    title: string;
    why: string;
    files?: string[];
  }[];
  tech_debt: { title: string; detail: string }[];
  risks: string[];
}

export interface AnalyzeOptions {
  path: string;
  model?: string;
  includeLlm?: boolean;
  signal?: AbortSignal;
  onEvent: (ev: AnalyzeProgressEvent) => void;
}

@Injectable({ providedIn: "root" })
export class ProjectAnalysisService {
  private http = inject(HttpClient);
  private settings = inject(SettingsService);

  private get base(): string {
    return this.settings.apiBaseUrl();
  }

  async analyze(opts: AnalyzeOptions): Promise<void> {
    const body = {
      path: opts.path,
      model: opts.model || undefined,
      include_llm: opts.includeLlm !== false,
    };
    let resp: Response;
    try {
      resp = await fetch(`${this.base}/analyze`, {
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
      const text = await resp.text().catch(() => "");
      opts.onEvent({
        type: "error",
        message: `HTTP ${resp.status} ${resp.statusText} ${text}`.trim(),
      });
      return;
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        let idx: number;
        while ((idx = buf.indexOf("\n\n")) !== -1) {
          const raw = buf.slice(0, idx).trim();
          buf = buf.slice(idx + 2);
          if (!raw.startsWith("data:")) continue;
          const json = raw.slice(5).trim();
          try {
            const ev = JSON.parse(json) as AnalyzeProgressEvent;
            opts.onEvent(ev);
          } catch {
            /* ignore parse error */
          }
        }
      }
    } catch (e: unknown) {
      if ((e as Error).name === "AbortError") {
        opts.onEvent({ type: "cancelled" });
        return;
      }
      opts.onEvent({ type: "error", message: (e as Error).message });
    }
  }

  getMemory(path: string): Promise<{
    ok: boolean;
    memory_dir: string;
    memory: ProjectMemory;
    markdown: Record<string, string>;
  }> {
    return firstValueFrom(
      this.http.get<{
        ok: boolean;
        memory_dir: string;
        memory: ProjectMemory;
        markdown: Record<string, string>;
      }>(`${this.base}/analyze/memory`, { params: { path } }),
    );
  }

  ask(
    path: string,
    question: string,
    model?: string,
  ): Promise<{ ok: boolean; answer: string }> {
    return firstValueFrom(
      this.http.post<{ ok: boolean; answer: string }>(
        `${this.base}/analyze/ask`,
        { path, question, model },
      ),
    );
  }
}
