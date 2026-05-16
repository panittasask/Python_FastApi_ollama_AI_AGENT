import { ChangeDetectionStrategy, Component, input } from "@angular/core";
import { CommonModule } from "@angular/common";
import { MarkdownComponent } from "../markdown/markdown.component";
import { ChatMessage } from "../../core/models";

@Component({
  selector: "app-message",
  standalone: true,
  imports: [CommonModule, MarkdownComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (msg(); as m) {
      <div
        class="group flex w-full gap-3 py-4 animate-fade-in"
        [class.justify-end]="m.role === 'user'"
      >
        @if (m.role !== "user") {
          <div
            class="mt-1 grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-brand-600 text-white text-sm font-bold shadow-soft"
          >
            AI
          </div>
        }

        <div class="flex max-w-[85%] flex-col gap-1">
          <div
            class="rounded-2xl px-4 py-3 shadow-soft"
            [ngClass]="bubbleClass(m)"
          >
            @if (m.role === "user") {
              @if (m.attachments && m.attachments.length) {
                <div class="mb-2 flex flex-wrap gap-1.5">
                  @for (a of m.attachments; track a.name + a.size) {
                    <span
                      class="inline-flex items-center gap-1 rounded-md bg-white/15 px-2 py-0.5 text-[11px] font-mono"
                      [title]="
                        a.name +
                        ' (' +
                        a.size +
                        ' bytes)' +
                        (a.truncated ? ' — truncated' : '')
                      "
                    >
                      📎 {{ a.name }}
                    </span>
                  }
                </div>
              }
              <p class="whitespace-pre-wrap leading-relaxed">{{ m.content }}</p>
            } @else {
              @if (m.agents && m.agents.length) {
                <div class="mb-2 flex flex-wrap gap-1.5">
                  @for (a of m.agents; track a.name + a.model) {
                    <span
                      class="inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium"
                      [ngClass]="agentBadgeClass(a.status)"
                      [title]="(a.message || '') + ' (' + a.status + ')'"
                    >
                      <span>{{ agentIcon(a.name) }}</span>
                      <span class="font-semibold">{{ a.name }}</span>
                      <span class="opacity-70">· {{ a.model || "?" }}</span>
                      <span class="opacity-70">· {{ a.status }}</span>
                    </span>
                  }
                </div>
              }
              @if (m.content) {
                <app-markdown [source]="m.content" />
              }
              @if (m.sources && m.sources.length) {
                <div
                  class="mt-3 rounded-lg border border-slate-200 dark:border-slate-700 p-2 text-[12px]"
                >
                  <div
                    class="mb-1 font-semibold text-slate-600 dark:text-slate-300"
                  >
                    🌐 Web sources
                  </div>
                  <ol class="list-decimal pl-5 space-y-1">
                    @for (s of m.sources; track s.url) {
                      <li>
                        <a
                          [href]="s.url"
                          target="_blank"
                          rel="noopener noreferrer"
                          class="text-brand-600 hover:underline"
                          >{{ s.title || s.url }}</a
                        >
                        @if (s.snippet) {
                          <div class="text-slate-500 dark:text-slate-400">
                            {{ s.snippet }}
                          </div>
                        }
                      </li>
                    }
                  </ol>
                </div>
              }
              @if (m.streaming) {
                <div class="mt-1 inline-flex items-center gap-1 text-slate-400">
                  <span
                    class="h-2 w-2 rounded-full bg-current animate-pulse-soft"
                  ></span>
                  <span
                    class="h-2 w-2 rounded-full bg-current animate-pulse-soft [animation-delay:150ms]"
                  ></span>
                  <span
                    class="h-2 w-2 rounded-full bg-current animate-pulse-soft [animation-delay:300ms]"
                  ></span>
                </div>
              }
            }
          </div>
          <div class="flex items-center gap-2 px-1 text-[11px] text-slate-400">
            <span>{{
              m.role === "user" ? "You" : m.model || "assistant"
            }}</span>
            <span>·</span>
            <span>{{ ts(m.createdAt) }}</span>
            @if (m.cancelled) {
              <span class="text-amber-500">· stopped</span>
            }
          </div>
        </div>

        @if (m.role === "user") {
          <div
            class="mt-1 grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-200 text-sm font-bold"
          >
            U
          </div>
        }
      </div>
    }
  `,
})
export class MessageComponent {
  msg = input<ChatMessage | null>(null);

  protected bubbleClass(m: ChatMessage): string {
    if (m.role === "user") {
      return "bg-brand-600 text-white";
    }
    return "bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800";
  }

  protected ts(t: number): string {
    try {
      return new Date(t).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return "";
    }
  }

  protected agentBadgeClass(status: string): string {
    switch (status) {
      case "end":
      case "done":
        return "border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300";
      case "error":
        return "border-rose-300 bg-rose-50 text-rose-700 dark:border-rose-700 dark:bg-rose-900/30 dark:text-rose-300";
      default:
        return "border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-700 dark:bg-amber-900/30 dark:text-amber-300 animate-pulse-soft";
    }
  }

  protected agentIcon(name: string): string {
    const n = (name || "").toLowerCase();
    if (n.includes("plan")) return "🧠";
    if (n.includes("refin")) return "✨";
    if (n.includes("cod")) return "💻";
    if (n.includes("fix")) return "🛠️";
    if (n.includes("test")) return "🧪";
    if (n.includes("chat")) return "💬";
    return "🤖";
  }
}
