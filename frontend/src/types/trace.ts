export interface TracesResponse {
  count: number;
  trace_ids: string[];
}

export interface ReplayResponse {
  replayable: boolean;
  reason?: string;
  original?: {
    trace_id?: string;
    question?: string;
    model?: string;
    temperature?: number;
    prompt_version?: string;
    retrieved?: Array<{
      filename?: string;
      page?: number;
      text?: string;
    }>;
    answer?: string;
  };
  replayed?: {
    answer?: string;
    model?: string;
    temperature?: number;
  };
  error?: string;
}

