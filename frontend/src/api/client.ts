import type {
  AnalyzeResponse,
  MemoResult,
  StatusResponse,
} from "./types";
import { ApiError } from "./types";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);

  if (!res.ok) {
    let message = res.statusText;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body.detail) message = body.detail;
    } catch {
      // ignore JSON parse failure — use statusText
    }
    throw new ApiError(res.status, message);
  }

  return res.json() as Promise<T>;
}

export async function uploadPdf(file: File): Promise<AnalyzeResponse> {
  const form = new FormData();
  form.append("file", file);
  return request<AnalyzeResponse>("/analyze", { method: "POST", body: form });
}

export async function fetchStatus(jobId: string): Promise<StatusResponse> {
  return request<StatusResponse>(`/status/${jobId}`);
}

export async function fetchResult(jobId: string): Promise<MemoResult> {
  return request<MemoResult>(`/result/${jobId}`);
}
