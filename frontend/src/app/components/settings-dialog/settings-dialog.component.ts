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
import { environment } from "@env/environment";
import { SettingsService } from "../../services/settings.service";
import { ThemeService, ThemeMode } from "../../services/theme.service";
import { ChatService } from "../../services/chat.service";
import { ApiService } from "../../services/api.service";

@Component({
  selector: "app-settings-dialog",
  standalone: true,
  imports: [CommonModule, FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div
      class="fixed inset-0 z-50 flex items-center justify-center p-4 animate-fade-in"
    >
      <div
        class="absolute inset-0 bg-slate-900/40 backdrop-blur-sm"
        (click)="close.emit()"
      ></div>
      <div class="relative w-full max-w-lg card p-5 animate-slide-up">
        <div class="mb-4 flex items-center justify-between">
          <h2 class="text-lg font-semibold">Settings</h2>
          <button class="btn-ghost !px-2" type="button" (click)="close.emit()">
            ✕
          </button>
        </div>

        <div class="space-y-4">
          <div>
            <label
              class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500"
              >API base URL</label
            >
            <div class="flex gap-2">
              <input
                class="input flex-1 font-mono"
                type="text"
                [(ngModel)]="form.apiBaseUrl"
                [placeholder]="envBase || 'http://127.0.0.1:8000'"
              />
              <button
                class="btn-ghost border border-slate-200 dark:border-slate-700"
                type="button"
                (click)="testConnection()"
                [disabled]="testing()"
                title="Test connection to /healthz"
              >
                {{ testing() ? "…" : "Test" }}
              </button>
            </div>
            <p class="mt-1 text-[11px] text-slate-500">
              Leave empty to use default
              <code class="font-mono">{{ envBase || "(none)" }}</code
              >. No trailing slash.
            </p>
            @if (testResult(); as r) {
              <p
                class="mt-1 text-[11px]"
                [class.text-emerald-500]="r.ok"
                [class.text-red-500]="!r.ok"
              >
                {{ r.msg }}
              </p>
            }
          </div>

          <div>
            <label
              class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500"
              >Theme</label
            >
            <div class="flex gap-2">
              @for (m of themes; track m) {
                <button
                  type="button"
                  class="btn-ghost flex-1 border border-slate-200 dark:border-slate-700"
                  [class.!bg-brand-600]="theme.mode() === m"
                  [class.!text-white]="theme.mode() === m"
                  (click)="theme.set(m)"
                >
                  {{ m }}
                </button>
              }
            </div>
          </div>

          <div>
            <label
              class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500"
              >Default model</label
            >
            <input
              class="input"
              type="text"
              [(ngModel)]="form.model"
              placeholder="qwen2.5:7b"
            />
          </div>

          <div>
            <label
              class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500"
              >System prompt</label
            >
            <textarea
              class="input min-h-[80px]"
              [(ngModel)]="form.systemPrompt"
              rows="3"
            ></textarea>
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div>
              <label
                class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500"
                >Temperature</label
              >
              <input
                class="input"
                type="number"
                step="0.05"
                min="0"
                max="2"
                [(ngModel)]="form.temperature"
              />
            </div>
            <div>
              <label
                class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500"
                >top_p</label
              >
              <input
                class="input"
                type="number"
                step="0.05"
                min="0"
                max="1"
                [(ngModel)]="form.topP"
              />
            </div>
            <div>
              <label
                class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500"
                >Max tokens</label
              >
              <input
                class="input"
                type="number"
                min="64"
                max="32768"
                [(ngModel)]="form.maxTokens"
              />
            </div>
            <div>
              <label
                class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500"
                >Context (num_ctx)</label
              >
              <input
                class="input"
                type="number"
                min="512"
                max="131072"
                [(ngModel)]="form.numCtx"
              />
            </div>
          </div>

          <label class="flex items-center gap-2 text-sm">
            <input type="checkbox" [(ngModel)]="form.streaming" />
            Stream responses
          </label>

          <div>
            <label
              class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500"
              >Output path</label
            >
            <input class="input" type="text" [(ngModel)]="form.outputPath" />
          </div>

          <div
            class="rounded-xl border border-slate-200 dark:border-slate-700 p-3"
          >
            <div class="mb-2 flex items-center justify-between">
              <h3
                class="text-xs font-semibold uppercase tracking-wider text-slate-500"
              >
                Per-agent models
              </h3>
              <span class="text-[11px] text-slate-400"
                >Used when 🧩 Per-agent is on</span
              >
            </div>
            <p class="mb-2 text-[11px] text-slate-500">
              Each role can use a different model. Leave blank to fall back to
              the backend default.
            </p>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="mb-1 block text-[11px] text-slate-500"
                  >✨ Refiner</label
                >
                <input
                  class="input font-mono text-xs"
                  type="text"
                  list="agentModelsList"
                  [(ngModel)]="form.refinerModel"
                  placeholder="qwen2.5:7b"
                />
              </div>
              <div>
                <label class="mb-1 block text-[11px] text-slate-500"
                  >🧠 Planner</label
                >
                <input
                  class="input font-mono text-xs"
                  type="text"
                  list="agentModelsList"
                  [(ngModel)]="form.plannerModel"
                  placeholder="qwen2.5:7b"
                />
              </div>
              <div>
                <label class="mb-1 block text-[11px] text-slate-500"
                  >💻 Coder</label
                >
                <input
                  class="input font-mono text-xs"
                  type="text"
                  list="agentModelsList"
                  [(ngModel)]="form.coderModel"
                  placeholder="deepseek-coder:6.7b"
                />
              </div>
              <div>
                <label class="mb-1 block text-[11px] text-slate-500"
                  >🛠️ Fixer</label
                >
                <input
                  class="input font-mono text-xs"
                  type="text"
                  list="agentModelsList"
                  [(ngModel)]="form.fixModel"
                  placeholder="codellama:13b"
                />
              </div>
            </div>
            <datalist id="agentModelsList">
              @for (m of availableModels(); track m) {
                <option [value]="m"></option>
              }
            </datalist>
          </div>
        </div>

        <div class="mt-5 flex items-center justify-between gap-2">
          <button
            class="btn-ghost text-red-500"
            type="button"
            (click)="resetAll()"
          >
            Reset
          </button>
          <div class="flex gap-2">
            <button class="btn-ghost" type="button" (click)="close.emit()">
              Cancel
            </button>
            <button class="btn-primary" type="button" (click)="save()">
              Save
            </button>
          </div>
        </div>

        @if (saved()) {
          <p class="mt-2 text-right text-xs text-emerald-500">Saved.</p>
        }
      </div>
    </div>
  `,
})
export class SettingsDialogComponent {
  @Output() readonly close = new EventEmitter<void>();

  protected theme = inject(ThemeService);
  private settings = inject(SettingsService);
  private chatSvc = inject(ChatService);
  private api = inject(ApiService);

  protected themes: ThemeMode[] = ["light", "dark", "system"];
  protected saved = signal(false);
  protected testing = signal(false);
  protected testResult = signal<{ ok: boolean; msg: string } | null>(null);
  protected envBase = environment.apiBaseUrl || "";
  protected availableModels = signal<string[]>([]);

  protected form = { ...this.settings.settings() };

  protected readonly _ = computed(() => this.settings.settings()); // keep DI tree alive

  constructor() {
    this.api.listModels().subscribe({
      next: (list) =>
        this.availableModels.set(
          (list || []).map((m) => m.name).filter((n): n is string => !!n),
        ),
      error: () => this.availableModels.set([]),
    });
  }

  save(): void {
    this.settings.update({
      ...this.form,
      temperature: Number(this.form.temperature),
      topP: Number(this.form.topP),
      maxTokens: Number(this.form.maxTokens),
      numCtx: Number(this.form.numCtx),
    });
    // Apply default model to active conversation if it has none.
    const active = this.chatSvc.active();
    if (active && !active.model && this.form.model) {
      this.chatSvc.setModel(active.id, this.form.model);
    }
    this.saved.set(true);
    setTimeout(() => this.saved.set(false), 1200);
  }

  resetAll(): void {
    if (!confirm("Reset all settings?")) return;
    this.settings.reset();
    this.form = { ...this.settings.settings() };
  }

  async testConnection(): Promise<void> {
    const base = (this.form.apiBaseUrl || this.envBase || "").replace(
      /\/+$/,
      "",
    );
    if (!base) {
      this.testResult.set({ ok: false, msg: "No URL configured." });
      return;
    }
    this.testing.set(true);
    this.testResult.set(null);
    try {
      const resp = await fetch(`${base}/healthz`, { method: "GET" });
      if (resp.ok) {
        this.testResult.set({ ok: true, msg: `OK (${resp.status}) — ${base}` });
      } else {
        this.testResult.set({
          ok: false,
          msg: `HTTP ${resp.status} ${resp.statusText}`,
        });
      }
    } catch (e) {
      this.testResult.set({
        ok: false,
        msg: `Failed: ${(e as Error).message}`,
      });
    } finally {
      this.testing.set(false);
    }
  }
}
