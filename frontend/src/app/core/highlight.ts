// Single import surface for highlight.js so the bundler can tree-shake.
import hljs from "highlight.js/lib/common";

export function highlightCode(code: string, language?: string): string {
  const lang = (language ?? "").trim();
  try {
    if (lang && hljs.getLanguage(lang)) {
      return hljs.highlight(code, { language: lang, ignoreIllegals: true })
        .value;
    }
    return hljs.highlightAuto(code).value;
  } catch {
    return escape(code);
  }
}

function escape(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
