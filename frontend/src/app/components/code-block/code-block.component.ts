import {
  ChangeDetectionStrategy,
  Component,
  computed,
  ElementRef,
  inject,
  input,
  signal,
} from "@angular/core";
import { CommonModule } from "@angular/common";
import { highlightCode } from "../../core/highlight";
@Component({
  selector: "app-code-block",
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div
      class="my-3 overflow-hidden rounded-xl border border-slate-800 bg-slate-950 text-slate-100"
    >
      <div
        class="flex items-center justify-between border-b border-slate-800 bg-slate-900/60 px-3 py-1.5 text-xs"
      >
        <span class="font-mono uppercase tracking-wide text-slate-400">
          {{ language() || "code" }}
        </span>
        <button
          type="button"
          class="rounded-md px-2 py-1 text-xs text-slate-300 hover:bg-slate-800 hover:text-white transition-colors"
          (click)="copy()"
        >
          {{ copied() ? "✓ Copied" : "Copy" }}
        </button>
      </div>
      <pre
        class="m-0 overflow-x-auto p-4 text-[13px] leading-relaxed font-mono"
      ><code
        [innerHTML]="highlighted()"></code></pre>
    </div>
  `,
})
export class CodeBlockComponent {
  language = input<string>("");
  code = input<string>("");

  protected copied = signal(false);
  private host = inject(ElementRef<HTMLElement>);

  protected highlighted = computed(() =>
    highlightCode(this.code() ?? "", this.language()),
  );

  protected copy(): void {
    const text = this.code() ?? "";
    const done = () => {
      this.copied.set(true);
      setTimeout(() => this.copied.set(false), 1500);
    };
    if (navigator.clipboard?.writeText) {
      navigator.clipboard
        .writeText(text)
        .then(done)
        .catch(() => this.fallbackCopy(text, done));
    } else {
      this.fallbackCopy(text, done);
    }
  }

  private fallbackCopy(text: string, done: () => void): void {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    this.host.nativeElement.appendChild(ta);
    ta.select();
    try {
      document.execCommand("copy");
    } catch {
      /* ignore */
    }
    this.host.nativeElement.removeChild(ta);
    done();
  }
}
