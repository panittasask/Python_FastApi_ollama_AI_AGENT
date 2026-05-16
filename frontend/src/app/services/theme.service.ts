import { Injectable, effect, signal } from "@angular/core";

const KEY = "agent_ui.theme";
export type ThemeMode = "light" | "dark" | "system";

@Injectable({ providedIn: "root" })
export class ThemeService {
  readonly mode = signal<ThemeMode>(this.load());

  constructor() {
    effect(() => {
      const m = this.mode();
      try {
        localStorage.setItem(KEY, m);
      } catch {
        /* noop */
      }
      this.apply(m);
    });

    // react to system preference changes when in 'system' mode
    if (typeof window !== "undefined" && window.matchMedia) {
      const mql = window.matchMedia("(prefers-color-scheme: dark)");
      mql.addEventListener?.("change", () => {
        if (this.mode() === "system") this.apply("system");
      });
    }
  }

  init(): void {
    this.apply(this.mode());
  }

  set(mode: ThemeMode): void {
    this.mode.set(mode);
  }

  toggle(): void {
    const m = this.mode();
    this.mode.set(m === "dark" ? "light" : "dark");
  }

  isDark(): boolean {
    const m = this.mode();
    if (m === "dark") return true;
    if (m === "light") return false;
    return (
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-color-scheme: dark)").matches
    );
  }

  private apply(mode: ThemeMode): void {
    if (typeof document === "undefined") return;
    const dark =
      mode === "dark" ||
      (mode === "system" &&
        window.matchMedia?.("(prefers-color-scheme: dark)").matches);
    document.documentElement.classList.toggle("dark", dark);
  }

  private load(): ThemeMode {
    try {
      const v = localStorage.getItem(KEY) as ThemeMode | null;
      if (v === "light" || v === "dark" || v === "system") return v;
    } catch {
      /* noop */
    }
    return "system";
  }
}
