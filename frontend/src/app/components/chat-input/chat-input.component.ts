import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  EventEmitter,
  Output,
  ViewChild,
  computed,
  inject,
  signal,
} from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { ChatService } from "../../services/chat.service";
import { SettingsService } from "../../services/settings.service";
import { ApiService } from "../../services/api.service";
import { ChatAttachment } from "../../core/models";

export interface SendPayload {
  text: string;
  attachments: ChatAttachment[];
}

// Per-file limit. Larger files are truncated.
const MAX_FILE_BYTES = 200_000; // 200 KB per file
const MAX_TOTAL_BYTES = 600_000; // 600 KB combined
const ALLOWED_EXT = [
  "txt",
  "md",
  "markdown",
  "rst",
  "log",
  "csv",
  "tsv",
  "json",
  "yaml",
  "yml",
  "toml",
  "ini",
  "env",
  "cfg",
  "conf",
  "py",
  "ipynb",
  "js",
  "jsx",
  "ts",
  "tsx",
  "mjs",
  "cjs",
  "html",
  "htm",
  "css",
  "scss",
  "sass",
  "less",
  "java",
  "kt",
  "scala",
  "c",
  "h",
  "cpp",
  "hpp",
  "cc",
  "cs",
  "go",
  "rs",
  "rb",
  "php",
  "swift",
  "m",
  "mm",
  "sh",
  "bash",
  "zsh",
  "ps1",
  "bat",
  "cmd",
  "sql",
  "graphql",
  "proto",
  "xml",
  "svg",
  "dockerfile",
  "makefile",
  "gradle",
  "lock",
];

function isLikelyText(name: string): boolean {
  const lower = name.toLowerCase();
  if (lower === "dockerfile" || lower === "makefile" || lower === ".gitignore")
    return true;
  const ext = lower.includes(".") ? lower.split(".").pop()! : "";
  return ALLOWED_EXT.includes(ext);
}

@Component({
  selector: "app-chat-input",
  standalone: true,
  imports: [CommonModule, FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <form class="w-full" (submit)="onSubmit($event)">
      @if (attachments().length) {
        <div class="mb-2 flex flex-wrap gap-2">
          @for (a of attachments(); track a.name + a.size) {
            <span
              class="inline-flex items-center gap-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-2 py-1 text-xs"
              [title]="a.truncated ? a.name + ' (truncated)' : a.name"
            >
              <span>📎</span>
              <span class="font-mono max-w-[180px] truncate">{{ a.name }}</span>
              <span class="text-slate-400">{{ formatSize(a.size) }}</span>
              @if (a.truncated) {
                <span class="text-amber-600">trunc</span>
              }
              <button
                type="button"
                class="text-slate-400 hover:text-red-500"
                (click)="remove(a)"
                title="Remove"
              >
                ×
              </button>
            </span>
          }
        </div>
      }

      @if (error()) {
        <div
          class="mb-2 rounded-lg border border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-900/20 px-3 py-1.5 text-xs text-red-600"
        >
          {{ error() }}
        </div>
      }

      <div
        class="card flex flex-col gap-2 p-2 shadow-soft"
        [class.ring-2]="dragOver()"
        [class.ring-brand-500]="dragOver()"
        (dragover)="onDragOver($event)"
        (dragleave)="onDragLeave($event)"
        (drop)="onDrop($event)"
      >
        <textarea
          #ta
          class="max-h-64 min-h-[44px] w-full resize-none bg-transparent px-3 py-2 text-[15px] leading-relaxed focus:outline-none"
          [placeholder]="placeholder()"
          [(ngModel)]="value"
          name="prompt"
          rows="1"
          (input)="autoResize()"
          (keydown)="onKey($event)"
          [disabled]="chat.streaming()"
        ></textarea>

        <div class="flex flex-wrap items-center gap-2">
          <button
            type="button"
            class="inline-flex h-10 items-center justify-center rounded-xl border px-3 text-xs font-semibold transition-colors"
            [ngClass]="
              chat.agentMode()
                ? 'border-brand-500 text-brand-600 bg-brand-50 dark:bg-brand-600/15'
                : 'border-slate-200 dark:border-slate-700 text-slate-500'
            "
            (click)="toggleAgent()"
            [title]="
              chat.agentMode()
                ? 'Agent mode ON — writes files to disk'
                : 'Agent mode OFF — chat only'
            "
          >
            {{ chat.agentMode() ? "⚡ Agent" : "💬 Chat" }}
          </button>

          <button
            type="button"
            class="inline-flex h-10 items-center justify-center rounded-xl border px-3 text-xs font-semibold transition-colors"
            [ngClass]="
              chat.webSearchMode()
                ? 'border-emerald-500 text-emerald-700 bg-emerald-50 dark:bg-emerald-600/15 dark:text-emerald-300'
                : 'border-slate-200 dark:border-slate-700 text-slate-500'
            "
            (click)="toggleWebSearch()"
            [title]="
              chat.webSearchMode()
                ? 'Web search ON — grounds answers with live results'
                : 'Web search OFF'
            "
          >
            🌐 Web
          </button>

          @if (chat.agentMode()) {
            <button
              type="button"
              class="inline-flex h-10 items-center justify-center rounded-xl border px-3 text-xs font-semibold transition-colors"
              [ngClass]="
                chat.perAgentModelsMode()
                  ? 'border-violet-500 text-violet-700 bg-violet-50 dark:bg-violet-600/15 dark:text-violet-300'
                  : 'border-slate-200 dark:border-slate-700 text-slate-500'
              "
              (click)="togglePerAgent()"
              [title]="
                chat.perAgentModelsMode()
                  ? 'Per-agent models ON — each role uses its configured model'
                  : 'Per-agent models OFF — all roles use the selected model'
              "
            >
              🧩 Per-agent
            </button>
            <button
              type="button"
              class="inline-flex h-10 items-center justify-center rounded-xl border px-3 text-xs font-semibold transition-colors"
              [ngClass]="
                chat.continuationMode()
                  ? 'border-indigo-500 text-indigo-700 bg-indigo-50 dark:bg-indigo-600/15 dark:text-indigo-300'
                  : 'border-slate-200 dark:border-slate-700 text-slate-500'
              "
              (click)="toggleContinuation()"
              [title]="
                chat.continuationMode()
                  ? 'Continuation ON — modify existing files first, avoid duplicates'
                  : 'Continuation OFF — auto-detect existing project from output path'
              "
            >
              🧱 Continue
            </button>
          }

          <button
            type="button"
            class="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200 dark:border-slate-700 text-base text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
            (click)="picker.click()"
            title="Attach file contents to this message"
            [disabled]="chat.streaming()"
          >
            📎
          </button>
          <input
            #picker
            type="file"
            multiple
            class="hidden"
            (change)="onPick($event)"
          />

          @if (projectPath()) {
            <div
              class="inline-flex h-10 items-center gap-1 rounded-xl border border-indigo-300 dark:border-indigo-700 bg-indigo-50 dark:bg-indigo-900/30 px-2 text-xs font-medium text-indigo-700 dark:text-indigo-300"
              [title]="'Project folder: ' + projectPath()"
            >
              <button
                type="button"
                class="inline-flex items-center gap-1 hover:underline"
                (click)="pickProjectFolder('folder')"
                [disabled]="pickingFolder() || chat.streaming()"
              >
                📁 {{ projectLabel() }}
              </button>
              <button
                type="button"
                class="ml-1 rounded-md px-1 text-indigo-500 hover:bg-indigo-100 dark:hover:bg-indigo-800/40"
                (click)="clearProjectFolder()"
                title="Clear project folder"
                [disabled]="chat.streaming()"
              >
                ✕
              </button>
            </div>
          } @else {
            <button
              type="button"
              class="inline-flex h-10 items-center justify-center gap-1 rounded-xl border border-slate-200 dark:border-slate-700 px-3 text-xs font-semibold text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors disabled:opacity-50"
              (click)="pickProjectFolder('folder')"
              [disabled]="pickingFolder() || chat.streaming()"
              title="Pick a project folder — agent will modify files in it"
            >
              📁 {{ pickingFolder() ? "Opening…" : "Folder" }}
            </button>
            <button
              type="button"
              class="inline-flex h-10 items-center justify-center rounded-xl border border-slate-200 dark:border-slate-700 px-3 text-xs font-semibold text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors disabled:opacity-50"
              (click)="pickProjectFolder('file')"
              [disabled]="pickingFolder() || chat.streaming()"
              title="Pick a file — its parent folder will become the project"
            >
              📄 File
            </button>
          }

          <div class="ml-auto">
            @if (chat.streaming()) {
              <button
                type="button"
                class="btn-danger !rounded-xl !h-10 !py-0"
                (click)="stop()"
                title="Stop generating"
              >
                ■ Stop
              </button>
            } @else {
              <button
                type="submit"
                class="btn-primary !rounded-xl !h-10 !py-0"
                [disabled]="!canSend()"
                title="Send"
              >
                ↑ Send
              </button>
            }
          </div>
        </div>
      </div>

      <p class="mt-1 px-2 text-[11px] text-slate-400">
        Enter to send · Shift+Enter newline · Drop files to attach ·
        @if (chat.agentMode()) {
          <span class="text-brand-600 font-medium"
            >Agent mode: writes files to <code>generated_projects/</code></span
          >
        } @else {
          <span
            >Auto-detects build intent — toggle ⚡ Agent to always run the
            multi-agent pipeline</span
          >
        }
      </p>
    </form>
  `,
})
export class ChatInputComponent implements AfterViewInit {
  @ViewChild("ta") ta!: ElementRef<HTMLTextAreaElement>;
  @Output() readonly sent = new EventEmitter<SendPayload>();

  protected chat = inject(ChatService);
  private settings = inject(SettingsService);
  private api = inject(ApiService);
  protected value = "";
  protected attachments = signal<ChatAttachment[]>([]);
  protected dragOver = signal(false);
  protected error = signal<string | null>(null);
  protected pickingFolder = signal(false);

  protected projectPath = computed(
    () => this.settings.settings().outputPath || "",
  );
  protected projectLabel = computed(() => {
    const p = this.projectPath();
    if (!p) return "";
    const parts = p.replace(/\\/g, "/").split("/").filter(Boolean);
    return parts[parts.length - 1] || p;
  });

  protected canSend = computed(
    () =>
      !this.chat.streaming() &&
      (this.value.trim().length > 0 || this.attachments().length > 0),
  );

  protected placeholder = computed(() => {
    if (this.chat.streaming()) return "Generating…";
    if (this.attachments().length)
      return "Ask a question about the attached file(s)…";
    return "Ask the agent anything…";
  });

  ngAfterViewInit(): void {
    queueMicrotask(() => this.ta?.nativeElement.focus());
  }

  protected autoResize(): void {
    const el = this.ta.nativeElement;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 256) + "px";
  }

  protected onKey(ev: KeyboardEvent): void {
    if (ev.key === "Enter" && !ev.shiftKey && !ev.isComposing) {
      ev.preventDefault();
      this.submit();
    }
  }

  protected onSubmit(ev: Event): void {
    ev.preventDefault();
    this.submit();
  }

  protected stop(): void {
    this.chat.stop();
  }
  protected toggleAgent(): void {
    this.chat.toggleAgentMode();
  }
  protected toggleWebSearch(): void {
    this.chat.toggleWebSearchMode();
  }
  protected togglePerAgent(): void {
    this.chat.togglePerAgentModelsMode();
  }

  protected toggleContinuation(): void {
    this.chat.toggleContinuationMode();
  }

  protected async pickProjectFolder(
    kind: "folder" | "file" = "folder",
  ): Promise<void> {
    if (this.pickingFolder()) return;
    this.pickingFolder.set(true);
    this.error.set(null);
    try {
      const res = await new Promise<{
        path?: string;
        isDir?: boolean;
        is_dir?: boolean;
        cancelled?: boolean;
      }>((resolve, reject) => {
        this.api
          .browse({
            kind,
            initialDir: this.projectPath() || undefined,
            title:
              kind === "folder"
                ? "Select project folder to modify"
                : "Select a file (its folder will be used)",
          })
          .subscribe({ next: resolve, error: reject });
      });
      if (res.cancelled || !res.path) return;
      let folder = res.path;
      const isDir = res.isDir ?? res.is_dir ?? kind === "folder";
      if (!isDir) {
        const norm = folder.replace(/\\/g, "/");
        const i = norm.lastIndexOf("/");
        folder = i > 0 ? folder.substring(0, i) : folder;
      }
      this.settings.update({ outputPath: folder });
      // Auto-enable agent mode + continuation when pointing at an existing folder.
      if (!this.chat.agentMode()) this.chat.setAgentMode(true);
      this.chat.setContinuationMode(true);
    } catch (e: unknown) {
      const msg =
        (e as { error?: { detail?: string }; message?: string })?.error
          ?.detail ||
        (e as { message?: string })?.message ||
        "Folder picker failed";
      this.error.set(msg);
    } finally {
      this.pickingFolder.set(false);
    }
  }

  protected clearProjectFolder(): void {
    this.settings.update({ outputPath: "" });
    this.chat.setContinuationMode(false);
  }

  protected formatSize(n: number): string {
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
    return `${(n / 1024 / 1024).toFixed(1)} MB`;
  }

  protected remove(a: ChatAttachment): void {
    this.attachments.update((list) => list.filter((x) => x !== a));
  }

  protected onDragOver(ev: DragEvent): void {
    if (ev.dataTransfer?.types?.includes("Files")) {
      ev.preventDefault();
      this.dragOver.set(true);
    }
  }
  protected onDragLeave(ev: DragEvent): void {
    ev.preventDefault();
    this.dragOver.set(false);
  }
  protected onDrop(ev: DragEvent): void {
    ev.preventDefault();
    this.dragOver.set(false);
    const files = ev.dataTransfer?.files;
    if (files && files.length) void this.addFiles(Array.from(files));
  }
  protected onPick(ev: Event): void {
    const input = ev.target as HTMLInputElement;
    if (input.files && input.files.length) {
      void this.addFiles(Array.from(input.files));
    }
    input.value = "";
  }

  private async addFiles(files: File[]): Promise<void> {
    this.error.set(null);
    const accepted: ChatAttachment[] = [];
    let totalBytes = this.attachments().reduce(
      (n, a) => n + a.content.length,
      0,
    );

    for (const f of files) {
      if (!isLikelyText(f.name)) {
        this.error.set(
          `"${f.name}" is not a recognised text file. Only source/text files are supported.`,
        );
        continue;
      }
      if (totalBytes >= MAX_TOTAL_BYTES) {
        this.error.set(
          `Total attachment size limit (${MAX_TOTAL_BYTES / 1024} KB) reached.`,
        );
        break;
      }
      try {
        let text = await f.text();
        let truncated = false;
        if (text.length > MAX_FILE_BYTES) {
          text = text.slice(0, MAX_FILE_BYTES);
          truncated = true;
        }
        const room = MAX_TOTAL_BYTES - totalBytes;
        if (text.length > room) {
          text = text.slice(0, room);
          truncated = true;
        }
        totalBytes += text.length;
        accepted.push({
          name: f.name,
          content: text,
          size: f.size,
          mime: f.type || undefined,
          truncated,
        });
      } catch (e) {
        this.error.set(`Failed to read ${f.name}: ${(e as Error).message}`);
      }
    }
    if (accepted.length) {
      this.attachments.update((list) => [...list, ...accepted]);
    }
  }

  private submit(): void {
    const text = this.value.trim();
    if (this.chat.streaming()) return;
    if (!text && this.attachments().length === 0) return;
    const payload: SendPayload = { text, attachments: this.attachments() };
    this.value = "";
    this.attachments.set([]);
    this.error.set(null);
    queueMicrotask(() => this.autoResize());
    this.sent.emit(payload);
  }
}
