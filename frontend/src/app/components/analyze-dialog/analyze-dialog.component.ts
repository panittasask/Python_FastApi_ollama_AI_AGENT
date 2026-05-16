import {
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  Output,
  computed,
  inject,
  signal,
} from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { MarkdownComponent } from "../markdown/markdown.component";
import {
  AnalyzeProgressEvent,
  ProjectAnalysisService,
  ProjectMemory,
} from "../../services/project-analysis.service";
import { SettingsService } from "../../services/settings.service";
import { ChatService } from "../../services/chat.service";

interface LogLine {
  text: string;
  kind: "info" | "ok" | "err";
}

type TabName = "overview" | "architecture" | "map" | "todos";

@Component({
  selector: "app-analyze-dialog",
  standalone: true,
  imports: [CommonModule, FormsModule, MarkdownComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div
      class="fixed inset-0 z-50 flex items-center justify-center p-4 animate-fade-in"
    >
      <div
        class="absolute inset-0 bg-slate-900/50 backdrop-blur-sm"
        (click)="onBackdrop()"
      ></div>
      <div
        class="relative w-full max-w-4xl max-h-[90vh] flex flex-col card p-5 animate-slide-up"
      >
        <div class="mb-3 flex items-center justify-between gap-3">
          <h2 class="text-lg font-semibold flex items-center gap-2">
            📁 Analyze existing project
          </h2>
          <button class="btn-ghost !px-2" type="button" (click)="close.emit()">
            ✕
          </button>
        </div>

        <!-- Path input -->
        <div class="flex flex-col gap-2 sm:flex-row sm:items-end">
          <div class="flex-1">
            <label
              class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500"
              >Absolute project folder path</label
            >
            <input
              class="input font-mono text-sm"
              type="text"
              [(ngModel)]="path"
              placeholder="G:\\Code Generate\\TowerDefense  (or /Users/me/proj)"
              [disabled]="running()"
              (keydown.enter)="start()"
            />
          </div>
          <label
            class="flex items-center gap-2 text-xs text-slate-500 whitespace-nowrap"
          >
            <input
              type="checkbox"
              [(ngModel)]="includeLlm"
              [disabled]="running()"
            />
            Run AI analyzer
          </label>
          @if (!running()) {
            <button
              class="btn-primary"
              type="button"
              (click)="start()"
              [disabled]="!path.trim()"
            >
              Analyze
            </button>
          } @else {
            <button class="btn-danger" type="button" (click)="cancel()">
              Stop
            </button>
          }
        </div>

        @if (errorMsg()) {
          <p class="mt-2 text-sm text-red-500">{{ errorMsg() }}</p>
        }

        <!-- Body -->
        <div class="mt-4 flex-1 min-h-0 overflow-hidden flex flex-col gap-3">
          <!-- Progress log -->
          @if (logs().length) {
            <div
              class="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/60 max-h-40 overflow-auto p-2 text-xs font-mono"
            >
              @for (l of logs(); track $index) {
                <div
                  [class.text-red-500]="l.kind === 'err'"
                  [class.text-emerald-500]="l.kind === 'ok'"
                  [class.text-slate-500]="l.kind === 'info'"
                >
                  {{ l.text }}
                </div>
              }
            </div>
          }

          <!-- Results -->
          @if (memory(); as mem) {
            <div class="flex items-center gap-2 text-xs">
              <span class="font-semibold">{{ mem.name }}</span>
              <span class="text-slate-500 truncate">{{ mem.root }}</span>
              <span class="ml-auto text-slate-400">
                {{ mem.scan.total_files }} files ·
                {{ formatLines(mem.scan.total_lines) }} lines ·
                {{ (mem.scan.frameworks || []).join(", ") || "no framework" }}
              </span>
            </div>

            <div
              class="flex gap-1 border-b border-slate-200 dark:border-slate-800"
            >
              @for (t of tabs; track t.id) {
                <button
                  type="button"
                  class="px-3 py-1.5 text-sm font-medium border-b-2 -mb-px"
                  [ngClass]="
                    tab() === t.id
                      ? 'border-brand-500 text-brand-600 dark:text-brand-400'
                      : 'border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
                  "
                  (click)="tab.set(t.id)"
                >
                  {{ t.label }}
                </button>
              }
            </div>

            <div
              class="flex-1 min-h-0 overflow-auto rounded-lg border border-slate-200 dark:border-slate-800 p-4"
            >
              @if (activeMarkdown(); as md) {
                <app-markdown [source]="md" />
              } @else {
                <p class="text-sm text-slate-500">_(no content)_</p>
              }
            </div>

            <div class="flex flex-wrap items-center gap-2">
              <button
                class="btn-primary"
                type="button"
                (click)="useAsContext()"
                title="Inject this project context into the chat system prompt"
              >
                Use as chat context
              </button>
              <button
                class="btn-ghost border border-slate-200 dark:border-slate-700"
                type="button"
                (click)="askInChat()"
              >
                Open chat with summary
              </button>
              <span class="ml-auto text-[11px] text-slate-500">
                Memory saved to
                <code class="font-mono">{{ memoryDir() }}</code>
              </span>
            </div>

            @if (contextApplied()) {
              <p class="text-right text-xs text-emerald-500">
                Project context applied to chat. Open a new conversation to use
                it.
              </p>
            }
          }
        </div>
      </div>
    </div>
  `,
})
export class AnalyzeDialogComponent {
  @Output() readonly close = new EventEmitter<void>();

  private svc = inject(ProjectAnalysisService);
  private settings = inject(SettingsService);
  private chat = inject(ChatService);

  protected path = "";
  protected includeLlm = true;
  protected running = signal(false);
  protected logs = signal<LogLine[]>([]);
  protected errorMsg = signal<string | null>(null);
  protected memory = signal<ProjectMemory | null>(null);
  protected memoryDir = signal<string>("");
  protected markdown = signal<Record<string, string>>({});
  protected tab = signal<TabName>("overview");
  protected contextApplied = signal(false);

  protected tabs: { id: TabName; label: string }[] = [
    { id: "overview", label: "Overview" },
    { id: "architecture", label: "Architecture" },
    { id: "map", label: "Codebase Map" },
    { id: "todos", label: "TODO Plan" },
  ];

  protected activeMarkdown = computed(() => {
    const md = this.markdown();
    switch (this.tab()) {
      case "overview":
        return md["PROJECT_ANALYSIS.md"] || "";
      case "architecture":
        return md["ARCHITECTURE.md"] || "";
      case "map":
        return md["CODEBASE_MAP.md"] || "";
      case "todos":
        return md["TODO_PLAN.md"] || "";
    }
  });

  private abort?: AbortController;

  protected formatLines(n: number): string {
    return n.toLocaleString();
  }

  protected onBackdrop(): void {
    if (this.running()) return;
    this.close.emit();
  }

  protected cancel(): void {
    this.abort?.abort();
  }

  protected async start(): Promise<void> {
    if (!this.path.trim() || this.running()) return;
    this.running.set(true);
    this.errorMsg.set(null);
    this.logs.set([]);
    this.memory.set(null);
    this.markdown.set({});
    this.contextApplied.set(false);
    this.abort = new AbortController();

    await this.svc.analyze({
      path: this.path.trim(),
      includeLlm: this.includeLlm,
      signal: this.abort.signal,
      onEvent: (ev) => this.handle(ev),
    });
    this.running.set(false);
  }

  private handle(ev: AnalyzeProgressEvent): void {
    const push = (text: string, kind: LogLine["kind"] = "info") =>
      this.logs.update((l) => [...l, { text, kind }]);

    switch (ev.type) {
      case "start":
        push(`started — ${ev.path}`, "info");
        break;
      case "progress":
        push(ev.message || "", "info");
        break;
      case "done":
        push("analysis complete ✓", "ok");
        if (ev.memory) this.memory.set(ev.memory);
        if (ev.memory_dir) this.memoryDir.set(ev.memory_dir);
        if (ev.markdown) this.markdown.set(ev.markdown);
        break;
      case "cancelled":
        push("cancelled", "err");
        break;
      case "error":
        push(`error: ${ev.message || "unknown"}`, "err");
        this.errorMsg.set(ev.message || "Analysis failed");
        break;
    }
  }

  protected useAsContext(): void {
    const mem = this.memory();
    if (!mem) return;
    const ctx = this.buildContext(mem);
    this.settings.update({ systemPrompt: ctx });
    this.contextApplied.set(true);
  }

  protected askInChat(): void {
    const mem = this.memory();
    if (!mem) return;
    const ctx = this.buildContext(mem);
    this.settings.update({ systemPrompt: ctx });
    const conv = this.chat.newConversation();
    this.chat.rename(conv.id, `Project: ${mem.name}`);
    this.close.emit();
  }

  private buildContext(mem: ProjectMemory): string {
    const a = mem.analysis || ({} as ProjectMemory["analysis"]);
    const s = mem.scan;
    const lines: string[] = [];
    lines.push(
      `You are assisting on the existing project \`${mem.name}\` located at \`${mem.root}\`.`,
    );
    lines.push(
      "Use the project facts below as ground truth. Prefer existing files and conventions over inventing new ones.",
    );
    lines.push("");
    lines.push("## Overview");
    lines.push(a.overview || "(none)");
    lines.push("");
    lines.push("## Architecture");
    lines.push(a.architecture || "(none)");
    lines.push("");
    lines.push(`## Frameworks: ${(s.frameworks || []).join(", ") || "(none)"}`);
    lines.push(
      `## Package managers: ${(s.package_managers || []).join(", ") || "(none)"}`,
    );
    lines.push("");
    lines.push("## Folder tree (truncated)");
    lines.push("```");
    lines.push((s.tree || "").slice(0, 4000));
    lines.push("```");
    const todos = a.todos || [];
    if (todos.length) {
      lines.push("");
      lines.push("## Suggested todos");
      todos
        .slice(0, 10)
        .forEach((t) =>
          lines.push(
            `- [${t.priority || "?"}] ${t.title}${t.why ? " — " + t.why : ""}`,
          ),
        );
    }
    return lines.join("\n");
  }
}
