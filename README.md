# AI Coding Agent API

An autonomous, multi-agent AI coding platform powered by **Ollama**.
It refines vague user requests, plans full projects, generates code file-by-file,
runs tests, and self-fixes errors in a loop — fully local.

Inspired by Devin / OpenHands / Cursor Agent / Claude Code, but 100% offline using your own models.

---

## Features

- **Multi-Agent Workflow**
  - `PromptRefinerAgent` — turns vague prompts into precise technical briefs.
  - `PlannerAgent` — produces a structured JSON project plan.
  - `CodeGenerationAgent` — generates production-ready code, file by file.
  - `FixAgent` — reads error logs and rewrites broken files.
- **Large project support** with `project_plan.md` (auto-created, auto-updated, machine-parseable).
- **Dependency-aware generation loop** — runs tasks whose deps are done first.
- **Automatic test + self-fix loop** (`pytest`, `npm test`, `go test`, `cargo test`).
- **Safe file system** confined to project root (no path escapes).
- **Streaming + WebSocket** live logs.
- **Per-request model selection** (refiner / coder / fix / planner) and tuning (temp, top_p, ctx).
- **Retry + JSON repair + rollback on file writes**.
- **Docker + docker-compose** with bundled Ollama service.
- **Modern Angular 18 web UI** ([frontend/](frontend/)) — ChatGPT-style chat, streaming, markdown,
  code highlighting, model picker, settings, dark mode, and live `project_plan.md` viewer.

---

## Project structure

```
app/
  agents/         # refiner, planner, coder, fixer
  core/           # config, logging, exceptions
  models/         # pydantic schemas
  routers/        # FastAPI endpoints
  services/       # ollama client, orchestrator, file mgr, plan mgr, test runner, jobs
  utils/          # parsing helpers
  main.py         # FastAPI entrypoint
tests/            # unit tests
generated_projects/  # output target (default)
```

---

## Quick start

### 1. Local Python

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # *nix
pip install -r requirements.txt
cp .env.example .env

# make sure Ollama is running locally and the models are pulled
ollama pull qwen2.5:7b
ollama pull deepseek-coder:6.7b
ollama pull codellama:13b

uvicorn app.main:app --reload
```

Open http://localhost:8000/docs for the Swagger UI.

### 2. Docker

```bash
docker compose up --build
# pull models inside the ollama container the first time:
docker exec -it agent_api_ollama ollama pull qwen2.5:7b
docker exec -it agent_api_ollama ollama pull deepseek-coder:6.7b
docker exec -it agent_api_ollama ollama pull codellama:13b
```

---

## API

| Method | Path                | Purpose                                               |
| ------ | ------------------- | ----------------------------------------------------- |
| POST   | `/generate`         | Refine + generate code for a small request            |
| POST   | `/generate/stream`  | Server-Sent Events of the refiner output              |
| POST   | `/generate/project` | Kick off a full project build (async, returns job id) |
| POST   | `/test`             | Run tests in a generated project                      |
| POST   | `/fix`              | Send an error log; the FixAgent rewrites files        |
| GET    | `/status`           | Summary of all jobs                                   |
| GET    | `/status/{job_id}`  | Single job detail + recent logs                       |
| GET    | `/logs/{job_id}`    | All captured logs for a job                           |
| GET    | `/plans`            | List of generated `project_plan.md` files             |
| GET    | `/plans/{project}`  | Read a specific plan (markdown)                       |
| WS     | `/ws/logs/{job_id}` | Live log stream                                       |
| GET    | `/healthz`          | Health check                                          |

See [sample_requests.http](sample_requests.http) for ready-to-run examples.

---

## How a full project build works

1. **Refine** — `PromptRefinerAgent` rewrites the user's request as a structured brief.
2. **Plan** — `PlannerAgent` emits strict JSON with `project_name`, `architecture`, `dependencies`, and an ordered list of `tasks` (each with `id`, `title`, `file_path`, `depends_on`).
3. **Persist** — `project_plan.md` is written into the output directory.
4. **Generate loop** — for each task whose deps are done:
   - status → `in_progress`, plan saved
   - `CodeGenerationAgent` emits one or more `File: <path>` blocks
   - files are written safely under the project root
   - status → `completed`, plan saved
5. **Test + fix loop** (if `auto_test`):
   - run detected test command
   - on failure, collect mentioned files + error blob → `FixAgent`
   - apply fixed files, re-run; up to `MAX_FIX_ITERATIONS` rounds.

---

## Configuration

All env vars live in [.env.example](.env.example). Per request, you can override any model and sampling parameter via the `config` field on `/generate` and `/generate/project`:

```json
{
  "config": {
    "refiner_model": "qwen2.5:14b",
    "coder_model": "deepseek-coder:33b",
    "fix_model": "codellama:13b",
    "temperature": 0.15,
    "top_p": 0.9,
    "max_tokens": 8192,
    "num_ctx": 16384
  }
}
```

---

## Tests

```bash
pytest
```

Unit tests cover JSON repair, file-block parsing, plan render/parse round-trip, and the sandboxed file manager.

---

## Safety & robustness

- All writes are confined to the project root (`FileOperationError` on escape).
- Existing files are backed up before overwrite and restored on failure.
- LLM output goes through JSON repair (smart-quote, trailing-comma, brace balancing).
- HTTP calls to Ollama use exponential backoff via `tenacity`.
- Generation and fix loops have hard caps (`MAX_GENERATION_LOOPS`, `MAX_FIX_ITERATIONS`).
- Test commands run with a timeout and capped output capture.

---

## License

MIT
