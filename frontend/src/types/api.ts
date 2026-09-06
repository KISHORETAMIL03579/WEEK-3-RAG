import { DocumentInfo, UploadDocumentResult, DocumentPage } from './document';

export interface SourceInfo {
  filename: string;
  page?: number | null;
  section?: string | null;
  score: number;
  text: string;
  doc_id: string;
  openable?: boolean;
  method?: string;
}

export interface StatusResponse {
  ok: boolean;
  documents?: DocumentInfo[];
  chunks_indexed?: number;
  total_chunks?: number;
  vector_backend?: string;
  mode?: string;
  embeddings_configured?: boolean;
  chat_configured?: boolean;
  error?: string;
}

export interface AskRequest {
  query: string;
  chunk_mode?: string;
  top_k?: number;
  temperature?: number;
}

export interface AskResponse {
  answer: string;
  sources: SourceInfo[];
  top_k: number;
  temperature: number;
  query?: string;
  trace_id?: string;
  error?: string;
}

export interface UploadResponse {
  ok: boolean;
  documents: UploadDocumentResult[];
  total_indexed?: number;
  cancelled?: boolean;
  cleanup_complete?: boolean;
  error?: string;
  failed_cleanup?: Array<{
    doc_id: string;
    filename: string;
    error: string;
  }>;
}

export interface LoadUrlRequest {
  url: string;
  chunk_mode?: string;
}

export interface LoadUrlResponse {
  ok: boolean;
  doc_id: string;
  filename: string;
  chunks: number;
  error?: string;
}

export interface RemoveResponse {
  ok: boolean;
  doc_id?: string;
  deleted_chunks?: number;
  error?: string;
}

export interface ClearResponse {
  ok: boolean;
  message?: string;
  error?: string;
}

export interface PagesResponse {
  doc_id: string;
  filename: string;
  ext: string;
  pages: DocumentPage[];
  error?: string;
}

export interface ErrorResponse {
  error?: string;
  message?: string;
  detail?: string | unknown[];
}

