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
        class="card flex items-end gap-2 p-2 shadow-soft"
        [class.ring-2]="dragOver()"
        [class.ring-brand-500]="dragOver()"
        (dragover)="onDragOver($event)"
        (dragleave)="onDragLeave($event)"
        (drop)="onDrop($event)"
      >
        <button
          type="button"
          class="rounded-xl border px-2 py-2 text-xs font-semibold transition-colors"
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
          class="rounded-xl border border-slate-200 dark:border-slate-700 px-2 py-2 text-sm text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
          (click)="picker.click()"
          title="Attach files"
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

        <textarea
          #ta
          class="max-h-64 min-h-[44px] flex-1 resize-none bg-transparent px-3 py-2 text-[15px] leading-relaxed focus:outline-none"
          [placeholder]="placeholder()"
          [(ngModel)]="value"
          name="prompt"
          rows="1"
          (input)="autoResize()"
          (keydown)="onKey($event)"
          [disabled]="chat.streaming()"
        ></textarea>

        @if (chat.streaming()) {
          <button
            type="button"
            class="btn-danger !rounded-xl"
            (click)="stop()"
            title="Stop generating"
          >
            ■ Stop
          </button>
        } @else {
          <button
            type="submit"
            class="btn-primary !rounded-xl"
            [disabled]="!canSend()"
            title="Send"
          >
            ↑ Send
          </button>
        }
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
  protected value = "";
  protected attachments = signal<ChatAttachment[]>([]);
  protected dragOver = signal(false);
  protected error = signal<string | null>(null);

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
