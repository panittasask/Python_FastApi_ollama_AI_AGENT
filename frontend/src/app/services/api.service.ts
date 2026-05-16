import { Injectable, inject } from "@angular/core";
import { HttpClient } from "@angular/common/http";
import { Observable } from "rxjs";
import { OllamaModel, PlanFile, PlanResponse } from "../core/models";
import { SettingsService } from "./settings.service";

@Injectable({ providedIn: "root" })
export class ApiService {
  private http = inject(HttpClient);
  private settings = inject(SettingsService);
  private get base(): string {
    return this.settings.apiBaseUrl();
  }

  listModels(): Observable<OllamaModel[]> {
    return this.http.get<OllamaModel[]>(`${this.base}/api/models`);
  }

  listPlans(): Observable<{ plans: PlanFile[] }> {
    return this.http.get<{ plans: PlanFile[] }>(`${this.base}/plans`);
  }

  getPlan(project: string): Observable<PlanResponse> {
    return this.http.get<PlanResponse>(
      `${this.base}/plans/${encodeURIComponent(project)}`,
    );
  }

  health(): Observable<{ ok: boolean }> {
    return this.http.get<{ ok: boolean }>(`${this.base}/healthz`);
  }
}
