import { marked, type Token, type TokensList } from "marked";
import DOMPurify from "dompurify";

export interface MdSegment {
  kind: "html" | "code";
  /** for 'html' segments */
  html?: string;
  /** for 'code' segments */
  code?: string;
  language?: string;
}

/**
 * Split markdown into ordered segments so the Angular template can render
 * fenced code blocks via a dedicated component (with copy button + highlight)
 * while the rest of the prose is rendered as sanitized HTML.
 */
export function renderSegments(markdown: string): MdSegment[] {
  if (!markdown) return [];
  const tokens = marked.lexer(markdown);
  const segments: MdSegment[] = [];
  let buffer: Token[] = [];

  const flushBuffer = () => {
    if (!buffer.length) return;
    const html = marked.parser(buffer as unknown as TokensList);
    segments.push({ kind: "html", html: DOMPurify.sanitize(html) });
    buffer = [];
  };

  for (const tok of tokens) {
    if (tok.type === "code") {
      flushBuffer();
      segments.push({
        kind: "code",
        code: (tok as { text: string }).text ?? "",
        language: ((tok as { lang?: string }).lang ?? "").trim(),
      });
    } else {
      buffer.push(tok);
    }
  }
  flushBuffer();
  return segments;
}

/** Render markdown to a single sanitized HTML string (used for plan viewer). */
export function renderMarkdownHtml(markdown: string): string {
  const html = marked.parse(markdown ?? "", { async: false }) as string;
  return DOMPurify.sanitize(html);
}
