import {
  ChangeDetectionStrategy,
  Component,
  OnDestroy,
  OnInit,
  computed,
  inject,
  signal,
} from "@angular/core";
import { CommonModule } from "@angular/common";
import { ActivatedRoute, RouterLink } from "@angular/router";
import { ApiService } from "../../services/api.service";
import { MarkdownComponent } from "../../components/markdown/markdown.component";

interface TaskRow {
  raw: string;
  status: "pending" | "in_progress" | "completed" | "failed";
  id: string;
  title: string;
  file?: string;
}

const STATUS_MAP: Record<string, TaskRow["status"]> = {
  " ": "pending",
  "~": "in_progress",
  x: "completed",
  X: "completed",
  "!": "failed",
};

function parseTasks(md: string): TaskRow[] {
  const re =
    /^- \[(.)]\s+\*\*([^*]+)\*\*\s+—\s+(.+?)(?:\s+_\(file:\s*`([^`]+)`\)_)?\s*$/gm;
  const out: TaskRow[] = [];
  let m: RegExpExecArray | null;
  while ((m = re.exec(md)) !== null) {
    out.push({
      raw: m[0],
      status: STATUS_MAP[m[1]] ?? "pending",
      id: m[2].trim(),
      title: m[3].trim(),
      file: m[4],
    });
  }
  return out;
}

@Component({
  selector: "app-project-detail",
  standalone: true,
  imports: [CommonModule, RouterLink, MarkdownComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="mx-auto h-full w-full max-w-5xl overflow-y-auto p-6">
      <div class="mb-4 flex items-center gap-2">
        <a routerLink="/projects" class="btn-ghost">← Projects</a>
        <h1 class="text-xl font-semibold truncate flex-1">{{ project() }}</h1>
        <button
          class="btn-ghost"
          type="button"
          (click)="refresh()"
          [disabled]="loading()"
        >
          {{ loading() ? "Loading…" : "↻ Refresh" }}
        </button>
        <label class="ml-2 flex items-center gap-2 text-xs text-slate-500">
          <input
            type="checkbox"
            [checked]="autoRefresh()"
            (change)="toggleAuto($event)"
          />
          Auto-refresh
        </label>
      </div>

      @if (error()) {
        <div
          class="card border-red-300 dark:border-red-800 p-3 text-sm text-red-600"
        >
          {{ error() }}
        </div>
      }

      @if (tasks().length) {
        <div class="card mb-4 p-4">
          <div class="mb-2 flex items-center justify-between text-sm">
            <span class="font-semibold">Progress</span>
            <span class="text-slate-500"
              >{{ completedCount() }}/{{ tasks().length }} ({{
                percent()
              }}%)</span
            >
          </div>
          <div
            class="h-2 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800"
          >
            <div
              class="h-full bg-brand-600 transition-all"
              [style.width.%]="percent()"
            ></div>
          </div>
          <ul class="mt-4 space-y-1 text-sm">
            @for (t of tasks(); track t.id) {
              <li class="flex items-start gap-2">
                <span
                  class="mt-[3px] inline-block h-2 w-2 shrink-0 rounded-full"
                  [ngClass]="dotClass(t.status)"
                ></span>
                <div class="min-w-0">
                  <span class="font-mono text-xs text-slate-500">{{
                    t.id
                  }}</span>
                  <span class="ml-1">{{ t.title }}</span>
                  @if (t.file) {
                    <code class="ml-1 font-mono text-xs text-slate-500"
                      >({{ t.file }})</code
                    >
                  }
                </div>
              </li>
            }
          </ul>
        </div>
      }

      <div class="card p-5">
        <app-markdown [source]="markdown()" />
      </div>
    </div>
  `,
})
export class ProjectDetailComponent implements OnInit, OnDestroy {
  private route = inject(ActivatedRoute);
  private api = inject(ApiService);

  protected project = signal("");
  protected markdown = signal("");
  protected loading = signal(false);
  protected error = signal<string | null>(null);
  protected autoRefresh = signal(false);
  private timer: number | null = null;

  protected tasks = computed<TaskRow[]>(() => parseTasks(this.markdown()));
  protected completedCount = computed(
    () => this.tasks().filter((t) => t.status === "completed").length,
  );
  protected percent = computed(() => {
    const n = this.tasks().length;
    return n ? Math.round((100 * this.completedCount()) / n) : 0;
  });

  ngOnInit(): void {
    this.route.paramMap.subscribe((p) => {
      this.project.set(p.get("name") ?? "");
      this.refresh();
    });
  }

  ngOnDestroy(): void {
    this.stopAuto();
  }

  refresh(): void {
    const name = this.project();
    if (!name) return;
    this.loading.set(true);
    this.error.set(null);
    this.api.getPlan(name).subscribe({
      next: (r) => {
        this.markdown.set(r.markdown || "");
        this.loading.set(false);
      },
      error: (e) => {
        this.error.set(e?.error?.detail || e?.message || "Failed to load plan");
        this.loading.set(false);
      },
    });
  }

  toggleAuto(ev: Event): void {
    const on = (ev.target as HTMLInputElement).checked;
    this.autoRefresh.set(on);
    if (on) {
      this.timer = window.setInterval(() => this.refresh(), 3000);
    } else {
      this.stopAuto();
    }
  }

  private stopAuto(): void {
    if (this.timer !== null) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }

  protected dotClass(s: TaskRow["status"]): string {
    switch (s) {
      case "completed":
        return "bg-emerald-500";
      case "in_progress":
        return "bg-amber-500 animate-pulse";
      case "failed":
        return "bg-red-500";
      default:
        return "bg-slate-300 dark:bg-slate-600";
    }
  }
}
