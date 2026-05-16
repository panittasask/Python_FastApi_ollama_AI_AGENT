# Frontend (Angular 18)

Modern AI chat UI for the Agent API. Standalone components, Signals, Tailwind, dark mode,
streaming chat from Ollama via SSE, markdown + syntax highlighting + copy buttons,
project plan viewer with live progress.

## Stack

- Angular 18 (standalone APIs, `provideRouter`, lazy routes, signals)
- TailwindCSS 3
- marked + DOMPurify + highlight.js (lazy via single import surface)
- Fetch + AbortController for true streaming + cancel

## Install & run

```bash
cd frontend
npm install
npm start                 # ng serve --proxy-config proxy.conf.json
# open http://localhost:4200
```

The dev server proxies `/api`, `/generate`, `/plans`, `/status`, `/logs`, `/test`, `/fix`, and `/ws`
to the FastAPI backend on `http://localhost:8000`. Start the backend first:

```bash
# in repo root
uvicorn app.main:app --reload
```

## Production build

```bash
npm run build:prod
# output → frontend/dist/agent-api-ui/
```

Serve `dist/agent-api-ui/browser` behind any static host (or via Nginx in front of FastAPI).

## Project structure

```
src/app
├── app.component.ts         # root, initialises theme
├── app.config.ts            # provideRouter + provideHttpClient(withFetch)
├── app.routes.ts            # lazy routes (chat + projects)
├── core/                    # models, markdown renderer, highlight surface
├── services/                # api, streaming, settings, theme, chat (state)
├── components/              # sidebar, message, chat-input, code-block,
│                            # markdown, model-selector, settings-dialog
├── layouts/chat-layout/     # main shell (sidebar + header + outlet)
└── features/
    ├── chat/                # chat page
    └── projects/            # plan list + live plan viewer
```

## Features

- **Chat** — auto-expanding textarea, Enter to send / Shift+Enter newline, streaming reply,
  stop button, regenerate button, copy buttons on every code block, typing indicator,
  per-conversation model.
- **Conversations** — persisted to `localStorage`, sidebar with rename/delete,
  auto-titled from the first user message.
- **Model selector** — loads from `GET /api/models`, refresh button, persists choice.
- **Settings dialog** — model, system prompt, temperature, top_p, max tokens, ctx,
  streaming toggle, output path, theme (light/dark/system).
- **Project viewer** — `/projects` lists generated projects; clicking one shows the
  live `project_plan.md` with a progress bar, color-coded task dots, and optional
  3-second auto-refresh.
- **Dark mode** — Tailwind `class` strategy, follows system preference by default.
- **Performance** — `ChangeDetectionStrategy.OnPush` everywhere, signals for state,
  lazy-loaded feature routes, code highlighting computed only when rendering.

## API contract used

| Method | Path               | Purpose                      |
| ------ | ------------------ | ---------------------------- |
| GET    | `/api/models`      | list installed Ollama models |
| POST   | `/api/chat`        | SSE chat stream              |
| GET    | `/plans`           | list generated projects      |
| GET    | `/plans/{project}` | read `project_plan.md`       |
