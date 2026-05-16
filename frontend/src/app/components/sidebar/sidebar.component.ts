import { ChangeDetectionStrategy, Component, inject } from "@angular/core";
import { CommonModule } from "@angular/common";
import { Router, RouterLink, RouterLinkActive } from "@angular/router";
import { ChatService } from "../../services/chat.service";
import { ThemeService } from "../../services/theme.service";

@Component({
  selector: "app-sidebar",
  standalone: true,
  imports: [CommonModule, RouterLink, RouterLinkActive],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <aside
      class="flex h-full w-72 flex-col border-r border-slate-200 dark:border-slate-800 bg-white/60 dark:bg-slate-950/60 backdrop-blur"
    >
      <div class="flex items-center justify-between p-3">
        <div class="flex items-center gap-2">
          <div
            class="grid h-8 w-8 place-items-center rounded-xl bg-brand-600 text-white font-bold shadow-soft"
          >
            A
          </div>
          <div>
            <div class="text-sm font-semibold leading-tight">Agent</div>
            <div class="text-[11px] uppercase tracking-widest text-slate-500">
              Ollama UI
            </div>
          </div>
        </div>
        <button
          class="btn-ghost !px-2"
          type="button"
          (click)="theme.toggle()"
          title="Toggle theme"
        >
          {{ theme.isDark() ? "☀" : "☾" }}
        </button>
      </div>

      <button class="btn-primary mx-3 mb-3" type="button" (click)="newChat()">
        <span class="text-lg leading-none">＋</span>
        New chat
      </button>

      <nav
        class="px-3 pb-2 text-xs font-semibold uppercase tracking-widest text-slate-500"
      >
        Chats
      </nav>
      <div class="flex-1 overflow-y-auto px-2 pb-3">
        @if (!chat.conversations().length) {
          <p class="px-3 py-6 text-center text-sm text-slate-500">
            No conversations yet.
          </p>
        }
        @for (c of chat.conversations(); track c.id) {
          <a
            [routerLink]="['/chat', c.id]"
            routerLinkActive="bg-slate-100 dark:bg-slate-800"
            class="group flex items-center gap-2 rounded-xl px-3 py-2 text-sm hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            [class.bg-slate-100]="chat.activeId() === c.id"
            [class.dark:bg-slate-800]="chat.activeId() === c.id"
            (click)="select(c.id)"
          >
            <span class="truncate flex-1">{{ c.title }}</span>
            <button
              class="opacity-0 group-hover:opacity-100 text-xs text-slate-400 hover:text-red-500 transition-opacity"
              type="button"
              title="Delete"
              (click)="remove($event, c.id)"
            >
              ✕
            </button>
          </a>
        }
      </div>

      <div class="border-t border-slate-200 dark:border-slate-800 p-3 text-sm">
        <a
          routerLink="/projects"
          routerLinkActive="text-brand-600 dark:text-brand-400"
          class="block rounded-xl px-3 py-2 hover:bg-slate-100 dark:hover:bg-slate-800"
        >
          📁 Generated projects
        </a>
      </div>
    </aside>
  `,
})
export class SidebarComponent {
  protected chat = inject(ChatService);
  protected theme = inject(ThemeService);
  private router = inject(Router);

  newChat(): void {
    const c = this.chat.newConversation();
    this.router.navigate(["/chat", c.id]);
  }

  select(id: string): void {
    this.chat.select(id);
  }

  remove(ev: Event, id: string): void {
    ev.preventDefault();
    ev.stopPropagation();
    if (!confirm("Delete this conversation?")) return;
    this.chat.remove(id);
    this.router.navigate(["/"]);
  }
}
