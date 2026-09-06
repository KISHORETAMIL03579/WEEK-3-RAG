export interface DocumentInfo {
  doc_id: string;
  filename?: string;
  name?: string;
  chunks?: number;
  ext?: string;
  created_at?: string;
}

export interface UploadDocumentResult {
  doc_id?: string;
  filename: string;
  chunks?: number;
  error?: string;
  warning?: string;
  cleanup_complete?: boolean;
  cleanup_error?: string;
}

export interface StagedFile {
  id: string;
  file: File;
  name: string;
  previewUrl: string | null;
}

export interface DocumentPage {
  num: number;
  text: string;
}

