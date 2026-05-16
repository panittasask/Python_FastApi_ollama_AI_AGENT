import {
  ChangeDetectionStrategy,
  Component,
  computed,
  input,
} from "@angular/core";
import { CommonModule } from "@angular/common";
import { CodeBlockComponent } from "../code-block/code-block.component";
import { renderSegments, MdSegment } from "../../core/markdown";

@Component({
  selector: "app-markdown",
  standalone: true,
  imports: [CommonModule, CodeBlockComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="prose-chat">
      @for (seg of segments(); track $index) {
        @if (seg.kind === "html") {
          <div [innerHTML]="seg.html"></div>
        } @else {
          <app-code-block
            [language]="seg.language || ''"
            [code]="seg.code || ''"
          />
        }
      }
    </div>
  `,
})
export class MarkdownComponent {
  source = input<string>("");
  protected segments = computed<MdSegment[]>(() =>
    renderSegments(this.source() ?? ""),
  );
}
