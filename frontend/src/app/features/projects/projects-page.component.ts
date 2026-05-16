import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  inject,
  signal,
} from "@angular/core";
import { CommonModule } from "@angular/common";
import { RouterLink } from "@angular/router";
import { ApiService } from "../../services/api.service";
import { PlanFile } from "../../core/models";

@Component({
  selector: "app-projects-page",
  standalone: true,
  imports: [CommonModule, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="mx-auto h-full w-full max-w-4xl overflow-y-auto p-6">
      <div class="mb-4 flex items-center justify-between">
        <h1 class="text-xl font-semibold">Generated projects</h1>
        <button
          class="btn-ghost"
          type="button"
          (click)="load()"
          [disabled]="loading()"
        >
          {{ loading() ? "Loading…" : "↻ Refresh" }}
        </button>
      </div>

      @if (error()) {
        <div
          class="card border-red-300 dark:border-red-800 p-3 text-sm text-red-600"
        >
          {{ error() }}
        </div>
      }

      @if (!loading() && !plans().length) {
        <p class="card p-6 text-center text-sm text-slate-500">
          No generated projects yet. Use the backend
          <code class="font-mono">/generate/project</code> endpoint to create
          one.
        </p>
      }

      <ul class="grid grid-cols-1 gap-2 sm:grid-cols-2">
        @for (p of plans(); track p.project) {
          <li>
            <a
              [routerLink]="['/projects', p.project]"
              class="card block p-4 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
            >
              <div class="text-sm font-semibold">{{ p.project }}</div>
              <div class="mt-1 text-xs text-slate-500 truncate">
                {{ p.path }}
              </div>
            </a>
          </li>
        }
      </ul>
    </div>
  `,
})
export class ProjectsPageComponent implements OnInit {
  private api = inject(ApiService);
  protected plans = signal<PlanFile[]>([]);
  protected loading = signal(false);
  protected error = signal<string | null>(null);

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.api.listPlans().subscribe({
      next: (r) => {
        this.plans.set(r.plans);
        this.loading.set(false);
      },
      error: (e) => {
        this.error.set(
          e?.error?.detail || e?.message || "Failed to load plans",
        );
        this.loading.set(false);
      },
    });
  }
}
