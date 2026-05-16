import { Routes } from "@angular/router";
import { ChatLayoutComponent } from "./layouts/chat-layout/chat-layout.component";

export const APP_ROUTES: Routes = [
  {
    path: "",
    component: ChatLayoutComponent,
    children: [
      {
        path: "",
        loadComponent: () =>
          import("./features/chat/chat-page.component").then(
            (m) => m.ChatPageComponent,
          ),
      },
      {
        path: "chat/:id",
        loadComponent: () =>
          import("./features/chat/chat-page.component").then(
            (m) => m.ChatPageComponent,
          ),
      },
      {
        path: "projects",
        loadComponent: () =>
          import("./features/projects/projects-page.component").then(
            (m) => m.ProjectsPageComponent,
          ),
      },
      {
        path: "projects/:name",
        loadComponent: () =>
          import("./features/projects/project-detail.component").then(
            (m) => m.ProjectDetailComponent,
          ),
      },
    ],
  },
  { path: "**", redirectTo: "" },
];
