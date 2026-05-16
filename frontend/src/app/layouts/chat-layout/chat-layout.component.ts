import {
  ChangeDetectionStrategy,
  Component,
  inject,
  signal,
} from "@angular/core";
import { CommonModule } from "@angular/common";
import { RouterOutlet } from "@angular/router";
import { SidebarComponent } from "../../components/sidebar/sidebar.component";
import { ModelSelectorComponent } from "../../components/model-selector/model-selector.component";
import { SettingsDialogComponent } from "../../components/settings-dialog/settings-dialog.component";
import { AnalyzeDialogComponent } from "../../components/analyze-dialog/analyze-dialog.component";
import { ChatService } from "../../services/chat.service";

@Component({
  selector: "app-chat-layout",
  standalone: true,
  imports: [
    CommonModule,
    RouterOutlet,
    SidebarComponent,
    ModelSelectorComponent,
    SettingsDialogComponent,
    AnalyzeDialogComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div
      class="flex h-screen w-full overflow-hidden bg-gradient-to-b from-slate-50 to-white dark:from-slate-950 dark:to-slate-900"
    >
      <!-- Sidebar (desktop) -->
      <div class="hidden md:flex">
        <app-sidebar />
      </div>

      <!-- Mobile drawer -->
      @if (drawer()) {
        <div class="fixed inset-0 z-40 md:hidden">
          <div
            class="absolute inset-0 bg-black/40"
            (click)="drawer.set(false)"
          ></div>
          <div class="absolute inset-y-0 left-0 animate-slide-up">
            <app-sidebar />
          </div>
        </div>
      }

      <!-- Main column -->
      <div class="flex min-w-0 flex-1 flex-col">
        <header
          class="flex items-center gap-2 border-b border-slate-200 dark:border-slate-800 bg-white/70 dark:bg-slate-950/60 backdrop-blur px-3 py-2"
        >
          <button
            class="btn-ghost !px-2 md:hidden"
            type="button"
            (click)="toggleDrawer()"
            title="Menu"
          >
            ☰
          </button>
          <div class="text-sm font-semibold truncate flex-1">
            {{ chat.active()?.title || "AI Coding Agent" }}
          </div>
          <app-model-selector />
          <button
            class="btn-ghost !px-2"
            type="button"
            (click)="analyzeOpen.set(true)"
            title="Analyze existing project"
          >
            📁
          </button>
          <button
            class="btn-ghost !px-2"
            type="button"
            (click)="settingsOpen.set(true)"
            title="Settings"
          >
            ⚙
          </button>
        </header>

        <main class="flex-1 overflow-hidden">
          <router-outlet />
        </main>
      </div>

      @if (settingsOpen()) {
        <app-settings-dialog (close)="settingsOpen.set(false)" />
      }
      @if (analyzeOpen()) {
        <app-analyze-dialog (close)="analyzeOpen.set(false)" />
      }
    </div>
  `,
})
export class ChatLayoutComponent {
  protected chat = inject(ChatService);
  protected drawer = signal(false);
  protected settingsOpen = signal(false);
  protected analyzeOpen = signal(false);

  protected toggleDrawer(): void {
    this.drawer.update((v) => !v);
  }
}
