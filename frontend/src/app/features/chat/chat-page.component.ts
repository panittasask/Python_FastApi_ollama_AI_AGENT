import {
  AfterViewChecked,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  OnInit,
  ViewChild,
  inject,
} from "@angular/core";
import { CommonModule } from "@angular/common";
import { ActivatedRoute } from "@angular/router";
import { ChatService } from "../../services/chat.service";
import { MessageComponent } from "../../components/message/message.component";
import {
  ChatInputComponent,
  SendPayload,
} from "../../components/chat-input/chat-input.component";

@Component({
  selector: "app-chat-page",
  standalone: true,
  imports: [CommonModule, MessageComponent, ChatInputComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="flex h-full flex-col">
      <div #scroll class="flex-1 overflow-y-auto">
        <div class="mx-auto w-full max-w-3xl px-4">
          @if (!chat.active() || !chat.active()!.messages.length) {
            <div
              class="flex h-[60vh] flex-col items-center justify-center text-center text-slate-500"
            >
              <div
                class="mb-3 grid h-14 w-14 place-items-center rounded-2xl bg-brand-600 text-white text-2xl font-bold shadow-soft"
              >
                A
              </div>
              <h1
                class="text-2xl font-semibold text-slate-800 dark:text-slate-100"
              >
                How can I help you build today?
              </h1>
              <p class="mt-1 text-sm">
                Choose a model, describe what you need, and the agent will do
                the rest.
              </p>
              <div
                class="mt-6 grid w-full max-w-xl grid-cols-1 gap-2 sm:grid-cols-2"
              >
                @for (s of starters; track s) {
                  <button
                    class="card px-3 py-3 text-left text-sm hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
                    type="button"
                    (click)="sendText(s)"
                  >
                    {{ s }}
                  </button>
                }
              </div>
            </div>
          } @else {
            <div class="py-4">
              @for (m of chat.active()!.messages; track m.id) {
                <app-message [msg]="m" />
              }
              @if (showRegenerate()) {
                <div class="flex justify-center py-2">
                  <button
                    class="btn-ghost border border-slate-200 dark:border-slate-700"
                    type="button"
                    (click)="regenerate()"
                  >
                    ↻ Regenerate response
                  </button>
                </div>
              }
            </div>
          }
        </div>
      </div>

      <div
        class="border-t border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-950/70 backdrop-blur px-4 py-3"
      >
        <div class="mx-auto w-full max-w-3xl">
          <app-chat-input (sent)="send($event)" />
        </div>
      </div>
    </div>
  `,
})
export class ChatPageComponent implements OnInit, AfterViewChecked {
  @ViewChild("scroll") scroll!: ElementRef<HTMLDivElement>;
  protected chat = inject(ChatService);
  private route = inject(ActivatedRoute);

  protected starters = [
    "Build a FastAPI todo app with JWT auth and SQLite",
    "Explain async/await in Python with examples",
    "Write a TypeScript LRU cache with unit tests",
    "Refactor this code to use the strategy pattern",
  ];

  private lastLen = 0;

  ngOnInit(): void {
    this.route.paramMap.subscribe((p) => {
      const id = p.get("id");
      if (id) this.chat.select(id);
    });
  }

  ngAfterViewChecked(): void {
    const conv = this.chat.active();
    const len = conv?.messages.reduce((n, m) => n + m.content.length, 0) ?? 0;
    if (len !== this.lastLen) {
      this.lastLen = len;
      this.scrollToBottom();
    }
  }

  private scrollToBottom(): void {
    const el = this.scroll?.nativeElement;
    if (!el) return;
    queueMicrotask(() => {
      el.scrollTop = el.scrollHeight;
    });
  }

  protected showRegenerate(): boolean {
    if (this.chat.streaming()) return false;
    const conv = this.chat.active();
    if (!conv || !conv.messages.length) return false;
    return conv.messages[conv.messages.length - 1].role === "assistant";
  }

  protected send(payload: SendPayload): void {
    void this.chat.send(payload.text, payload.attachments);
  }

  protected sendText(text: string): void {
    void this.chat.send(text);
  }

  protected regenerate(): void {
    void this.chat.regenerate();
  }
}
