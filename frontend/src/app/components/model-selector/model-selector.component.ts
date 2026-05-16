import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { ApiService } from "../../services/api.service";
import { ChatService } from "../../services/chat.service";
import { SettingsService } from "../../services/settings.service";
import { OllamaModel } from "../../core/models";

@Component({
  selector: "app-model-selector",
  standalone: true,
  imports: [CommonModule, FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="flex items-center gap-2">
      <select
        class="input min-w-[200px] cursor-pointer"
        [ngModel]="current()"
        (ngModelChange)="onChange($event)"
        [disabled]="loading() || !models().length"
        aria-label="Select model"
      >
        @if (!models().length) {
          <option value="">
            {{ loading() ? "Loading…" : "No models found" }}
          </option>
        } @else {
          @for (m of models(); track m.name) {
            <option [value]="m.name">{{ m.name }}</option>
          }
        }
      </select>
      <button
        class="btn-ghost !px-2"
        type="button"
        title="Refresh model list"
        (click)="refresh()"
        [disabled]="loading()"
      >
        <span class="inline-block" [class.animate-spin]="loading()">⟳</span>
      </button>
    </div>
    @if (error()) {
      <p class="mt-1 text-xs text-red-500">{{ error() }}</p>
    }
  `,
})
export class ModelSelectorComponent implements OnInit {
  private api = inject(ApiService);
  private chat = inject(ChatService);
  private settings = inject(SettingsService);

  protected models = signal<OllamaModel[]>([]);
  protected loading = signal(false);
  protected error = signal<string | null>(null);

  protected current = computed(() => {
    const conv = this.chat.active();
    return conv?.model || this.settings.settings().model || "";
  });

  ngOnInit(): void {
    this.refresh();
  }

  refresh(): void {
    this.loading.set(true);
    this.error.set(null);
    this.api.listModels().subscribe({
      next: (list) => {
        this.models.set(list);
        const cur = this.current();
        if (!cur && list.length) {
          this.settings.update({ model: list[0].name });
        }
        this.loading.set(false);
      },
      error: (e) => {
        this.error.set(
          e?.error?.detail || e?.message || "Failed to load models",
        );
        this.loading.set(false);
      },
    });
  }

  onChange(model: string): void {
    const conv = this.chat.active();
    if (conv) this.chat.setModel(conv.id, model);
    this.settings.update({ model });
  }
}
