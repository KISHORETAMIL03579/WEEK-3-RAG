export interface EvalQuestionInput {
  id: string;
  question: string;
  expected: string;
}

export interface EvalRunPayload {
  questions: Array<{
    id: string;
    question: string;
    expected: string;
  }>;
  top_k: number;
  presets: string[];
  strategy_filter?: string;
}

export interface EvalQuestionResult {
  id: string;
  question: string;
  expected?: string;
  expected_doc?: string;
  expected_section?: string;
  hit: boolean;
  rank: number | null;
}

export interface EvalModeResult {
  hit_rate: number;
  mrr: number;
  hits: number;
  total: number;
  results: EvalQuestionResult[];
}

export interface EvalRunResponse {
  k: number;
  modes: Record<string, EvalModeResult>;
  error?: string;
}

export interface ParseQaResponse {
  pairs?: Array<{
    question: string;
    expected: string;
  }>;
  error?: string;
}

