import { Injectable, computed, effect, signal } from "@angular/core";
import { environment } from "@env/environment";
import { ChatSettings, DEFAULT_SETTINGS } from "../core/models";

const KEY = "agent_ui.settings";

@Injectable({ providedIn: "root" })
export class SettingsService {
  private readonly _settings = signal<ChatSettings>(this.load());
  readonly settings = computed(() => this._settings());

  /** Effective API base URL: user override or environment default, no trailing slash. */
  readonly apiBaseUrl = computed(() => {
    const raw = (
      this._settings().apiBaseUrl ||
      environment.apiBaseUrl ||
      ""
    ).trim();
    return raw.replace(/\/+$/, "");
  });

  constructor() {
    effect(() => {
      try {
        localStorage.setItem(KEY, JSON.stringify(this._settings()));
      } catch {
        /* quota / private mode */
      }
    });
  }

  update(patch: Partial<ChatSettings>): void {
    this._settings.update((s) => ({ ...s, ...patch }));
  }

  reset(): void {
    this._settings.set({ ...DEFAULT_SETTINGS });
  }

  private load(): ChatSettings {
    try {
      const raw = localStorage.getItem(KEY);
      if (!raw) return { ...DEFAULT_SETTINGS };
      const parsed = JSON.parse(raw) as Partial<ChatSettings>;
      return { ...DEFAULT_SETTINGS, ...parsed };
    } catch {
      return { ...DEFAULT_SETTINGS };
    }
  }
}
