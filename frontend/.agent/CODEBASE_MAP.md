# Codebase Map — `frontend`

## Folder tree
```
frontend/
├── src/
│   ├── app/
│   │   ├── components/
│   │   │   ├── analyze-dialog/
│   │   │   │   └── analyze-dialog.component.ts
│   │   │   ├── chat-input/
│   │   │   │   └── chat-input.component.ts
│   │   │   ├── code-block/
│   │   │   │   └── code-block.component.ts
│   │   │   ├── markdown/
│   │   │   │   └── markdown.component.ts
│   │   │   ├── message/
│   │   │   │   └── message.component.ts
│   │   │   ├── model-selector/
│   │   │   │   └── model-selector.component.ts
│   │   │   ├── settings-dialog/
│   │   │   │   └── settings-dialog.component.ts
│   │   │   └── sidebar/
│   │   │       └── sidebar.component.ts
│   │   ├── core/
│   │   │   ├── highlight.ts
│   │   │   ├── markdown.ts
│   │   │   └── models.ts
│   │   ├── features/
│   │   │   ├── chat/
│   │   │   │   └── chat-page.component.ts
│   │   │   └── projects/
│   │   │       ├── project-detail.component.ts
│   │   │       └── projects-page.component.ts
│   │   ├── layouts/
│   │   │   └── chat-layout/
│   │   │       └── chat-layout.component.ts
│   │   ├── services/
│   │   │   ├── api.service.ts
│   │   │   ├── chat.service.ts
│   │   │   ├── project-analysis.service.ts
│   │   │   ├── settings.service.ts
│   │   │   ├── streaming.service.ts
│   │   │   └── theme.service.ts
│   │   ├── app.component.ts
│   │   ├── app.config.ts
│   │   └── app.routes.ts
│   ├── environments/
│   │   ├── environment.prod.ts
│   │   └── environment.ts
│   ├── index.html
│   ├── main.ts
│   └── styles.css
├── .gitignore
├── angular.json
├── package-lock.json
├── package.json
├── postcss.config.js
├── proxy.conf.json
├── README.md
├── tailwind.config.js
├── tsconfig.app.json
└── tsconfig.json
```

## Entry points
_(none detected)_

## Config files
- `README.md`
- `angular.json`
- `package.json`
- `tsconfig.json`

## Dependencies
### `package.json::dependencies`
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

### `package.json::devDependencies`
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

### `package.json::peerDependencies`
```
```

### `package.json::scripts`
```
ng: ng
start: ng serve --host 0.0.0.0 --port 4200
build: ng build
build:prod: ng build --configuration production
watch: ng build --watch --configuration development
test: ng test
```
