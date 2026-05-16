# Codebase Map — `agent_api`

## Folder tree
```
agent_api/
├── app/
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── analyzer.py
│   │   ├── base.py
│   │   ├── coder.py
│   │   ├── fixer.py
│   │   ├── planner.py
│   │   └── refiner.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── exceptions.py
│   │   └── logging_config.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── analyze.py
│   │   ├── chat.py
│   │   ├── generate.py
│   │   ├── status.py
│   │   └── test_fix.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── file_manager.py
│   │   ├── job_registry.py
│   │   ├── ollama_client.py
│   │   ├── orchestrator.py
│   │   ├── plan_manager.py
│   │   ├── project_memory.py
│   │   ├── project_scanner.py
│   │   └── test_runner.py
│   ├── utils/
│   │   ├── __init__.py
│   │   └── parsing.py
│   ├── __init__.py
│   └── main.py
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── components/
│   │   │   │   ├── analyze-dialog/
│   │   │   │   │   └── analyze-dialog.component.ts
│   │   │   │   ├── chat-input/
│   │   │   │   │   └── chat-input.component.ts
│   │   │   │   ├── code-block/
│   │   │   │   │   └── code-block.component.ts
│   │   │   │   ├── markdown/
│   │   │   │   │   └── markdown.component.ts
│   │   │   │   ├── message/
│   │   │   │   │   └── message.component.ts
│   │   │   │   ├── model-selector/
│   │   │   │   │   └── model-selector.component.ts
│   │   │   │   ├── settings-dialog/
│   │   │   │   │   └── settings-dialog.component.ts
│   │   │   │   └── sidebar/
│   │   │   │       └── sidebar.component.ts
│   │   │   ├── core/
│   │   │   │   ├── highlight.ts
│   │   │   │   ├── markdown.ts
│   │   │   │   └── models.ts
│   │   │   ├── features/
│   │   │   │   ├── chat/
│   │   │   │   │   └── chat-page.component.ts
│   │   │   │   └── projects/
│   │   │   │       ├── project-detail.component.ts
│   │   │   │       └── projects-page.component.ts
│   │   │   ├── layouts/
│   │   │   │   └── chat-layout/
│   │   │   │       └── chat-layout.component.ts
│   │   │   ├── services/
│   │   │   │   ├── api.service.ts
│   │   │   │   ├── chat.service.ts
│   │   │   │   ├── project-analysis.service.ts
│   │   │   │   ├── settings.service.ts
│   │   │   │   ├── streaming.service.ts
│   │   │   │   └── theme.service.ts
│   │   │   ├── app.component.ts
│   │   │   ├── app.config.ts
│   │   │   └── app.routes.ts
│   │   ├── environments/
│   │   │   ├── environment.prod.ts
│   │   │   └── environment.ts
│   │   ├── index.html
│   │   ├── main.ts
│   │   └── styles.css
│   ├── .gitignore
│   ├── angular.json
│   ├── package-lock.json
│   ├── package.json
│   ├── postcss.config.js
│   ├── proxy.conf.json
│   ├── README.md
│   ├── tailwind.config.js
│   ├── tsconfig.app.json
│   └── tsconfig.json
├── generated_projects/
├── logs/
│   └── agent_api_2026-05-17.log
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_file_manager.py
│   ├── test_parsing.py
│   └── test_plan_manager.py
├── .env.example
├── .gitignore
├── docker-compose.yml
├── Dockerfile
├── pytest.ini
├── README.md
├── requirements.txt
└── sample_requests.http
```

## Entry points
- `app/main.py`

## Config files
- `.env.example`
- `Dockerfile`
- `README.md`
- `docker-compose.yml`
- `frontend/README.md`
- `frontend/angular.json`
- `frontend/package.json`
- `frontend/tsconfig.json`
- `requirements.txt`

## Dependencies
### `frontend/package.json::dependencies`
```
@angular/animations@^18.2.0
@angular/common@^18.2.0
@angular/compiler@^18.2.0
@angular/core@^18.2.0
@angular/forms@^18.2.0
@angular/platform-browser@^18.2.0
@angular/platform-browser-dynamic@^18.2.0
@angular/router@^18.2.0
dompurify@^3.1.6
highlight.js@^11.10.0
marked@^14.1.2
rxjs@~7.8.0
tslib@^2.7.0
zone.js@~0.14.10
```

### `frontend/package.json::devDependencies`
```
@angular-devkit/build-angular@^18.2.0
@angular/cli@^18.2.0
@angular/compiler-cli@^18.2.0
@types/dompurify@^3.0.5
autoprefixer@^10.4.20
postcss@^8.4.47
tailwindcss@^3.4.13
typescript@~5.5.4
```

### `frontend/package.json::peerDependencies`
```
```

### `frontend/package.json::scripts`
```
ng: ng
start: ng serve --host 0.0.0.0 --port 4200
build: ng build
build:prod: ng build --configuration production
watch: ng build --watch --configuration development
test: ng test
```

### `requirements.txt`
```
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
httpx>=0.27.0
pydantic>=2.9.0
pydantic-settings>=2.5.0
python-dotenv>=1.0.1
aiofiles>=24.1.0
tenacity>=9.0.0
loguru>=0.7.2
websockets>=13.0
rich>=13.9.0
pytest>=8.3.0
pytest-asyncio>=0.24.0
```
