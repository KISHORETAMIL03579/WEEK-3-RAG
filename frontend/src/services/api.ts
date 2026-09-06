import {
  StatusResponse,
  AskResponse,
  UploadResponse,
  LoadUrlResponse,
  RemoveResponse,
  ClearResponse,
  PagesResponse,
} from '../types/api';
import { EvalRunPayload, EvalRunResponse, ParseQaResponse } from '../types/evaluation';
import { TracesResponse, ReplayResponse } from '../types/trace';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

async function handleResponse<T>(res: Response): Promise<T> {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const errorMsg =
      data.error || data.message || (typeof data.detail === 'string' ? data.detail : null) || `Request failed with status ${res.status}`;
    throw new Error(errorMsg);
  }
  return data as T;
}

export const api = {
  async getStatus(signal?: AbortSignal): Promise<StatusResponse> {
    const res = await fetch(`${API_BASE}/status`, { signal });
    return handleResponse<StatusResponse>(res);
  },

  async uploadFiles(formData: FormData, signal?: AbortSignal): Promise<UploadResponse> {
    const res = await fetch(`${API_BASE}/upload`, {
      method: 'POST',
      body: formData,
      signal,
    });
    return handleResponse<UploadResponse>(res);
  },

  async cancelUpload(uploadId: string): Promise<{ ok: boolean }> {
    const res = await fetch(`${API_BASE}/upload-cancel`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ upload_id: uploadId }),
    });
    return handleResponse<{ ok: boolean }>(res);
  },

  async askQuestion(
    query: string,
    chunk_mode: string = 'structured',
    top_k: number = 8,
    temperature: number = 0.0,
    signal?: AbortSignal
  ): Promise<AskResponse> {
    const res = await fetch(`${API_BASE}/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, chunk_mode, top_k, temperature }),
      signal,
    });
    return handleResponse<AskResponse>(res);
  },

  async loadUrl(url: string, chunk_mode: string = 'structured', signal?: AbortSignal): Promise<LoadUrlResponse> {
    const res = await fetch(`${API_BASE}/load-url`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, chunk_mode }),
      signal,
    });
    return handleResponse<LoadUrlResponse>(res);
  },

  async removeDoc(doc_id: string, signal?: AbortSignal): Promise<RemoveResponse> {
    const res = await fetch(`${API_BASE}/remove`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ doc_id }),
      signal,
    });
    return handleResponse<RemoveResponse>(res);
  },

  async clearSession(signal?: AbortSignal): Promise<ClearResponse> {
    const res = await fetch(`${API_BASE}/clear`, {
      method: 'POST',
      signal,
    });
    return handleResponse<ClearResponse>(res);
  },

  async getTraces(signal?: AbortSignal): Promise<TracesResponse> {
    const res = await fetch(`${API_BASE}/traces`, { signal });
    return handleResponse<TracesResponse>(res);
  },

  async replayTrace(traceId: string, signal?: AbortSignal): Promise<ReplayResponse> {
    const res = await fetch(`${API_BASE}/replay/${encodeURIComponent(traceId)}`, {
      method: 'POST',
      signal,
    });
    return handleResponse<ReplayResponse>(res);
  },

  async getFilePages(docId: string, signal?: AbortSignal): Promise<PagesResponse> {
    const res = await fetch(`${API_BASE}/file/${encodeURIComponent(docId)}/pages`, {
      signal,
    });
    return handleResponse<PagesResponse>(res);
  },

  async runEvaluation(payload: EvalRunPayload, signal?: AbortSignal): Promise<EvalRunResponse> {
    const res = await fetch(`${API_BASE}/eval/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal,
    });
    return handleResponse<EvalRunResponse>(res);
  },

  async parseEvaluationFile(file: File, signal?: AbortSignal): Promise<ParseQaResponse> {
    const fd = new FormData();
    fd.append('file', file);
    const res = await fetch(`${API_BASE}/eval/parse-qa-pdf`, {
      method: 'POST',
      body: fd,
      signal,
    });
    return handleResponse<ParseQaResponse>(res);
  },

  async getOrphans(adminKey?: string, signal?: AbortSignal): Promise<unknown> {
    const headers: Record<string, string> = {};
    if (adminKey) {
      headers['X-Admin-Key'] = adminKey;
    }
    const res = await fetch(`${API_BASE}/orphans`, { headers, signal });
    return handleResponse(res);
  },
};

