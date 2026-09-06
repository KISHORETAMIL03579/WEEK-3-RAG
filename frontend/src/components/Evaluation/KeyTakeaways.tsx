import React from 'react';
import { EvalModeResult } from '../../types/evaluation';

export const PRESETS: Record<string, { label: string; desc: string }> = {
  'tfidf': { label: 'TF-IDF baseline', desc: 'Sparse keyword matching' },
  'bm25-qdrant-blend': { label: 'BM25 + Qdrant (Weighted Blend)', desc: 'Hybrid dense/sparse blend' },
  'bm25-qdrant-rrf': { label: 'BM25 + Qdrant (RRF)', desc: 'Reciprocal rank fusion' },
  'rrf-rerank': { label: '+ Cross-Encoder Rerank', desc: 'Contextual reranking' },
  'rrf-rerank-rewrite': { label: '+ Query Rewriting', desc: 'Subquery expansion & rewrite' },
};

interface KeyTakeawaysProps {
  modes?: Record<string, EvalModeResult>;
  k: number;
}

export const KeyTakeaways: React.FC<KeyTakeawaysProps> = ({ modes, k }) => {
  const modeKeys = Object.keys(modes || {});
  if (!modeKeys.length || !modes) return null;

  const rows = modeKeys.map((key) => {
    const meta = PRESETS[key] || { label: key };
    return {
      key,
      label: meta.label,
      hr: modes[key]?.hit_rate || 0,
      mrr: modes[key]?.mrr || 0,
    };
  });

  // Best strategy determined by highest Hit-Rate, with MRR as decisive tie-breaker
  const best = rows.reduce((a, b) => {
    if (b.hr !== a.hr) return b.hr > a.hr ? b : a;
    if (b.mrr !== a.mrr) return b.mrr > a.mrr ? b : a;
    return a;
  }, rows[0]);

  // Build lookup maps by question ID for robust strategy comparison
  const modeMaps: Record<string, Map<string, unknown>> = {};
  modeKeys.forEach((mk) => {
    modeMaps[mk] = new Map((modes[mk]?.results || []).map((r) => [r.id, r]));
  });

  const firstResults = modes[modeKeys[0]]?.results || [];
  const hardQ = firstResults.filter((q) => {
    return modeKeys.every((mk) => {
      const match = modeMaps[mk]?.get(q.id) as { hit?: boolean } | undefined;
      return !(match && match.hit);
    });
  });

  // Explicitly identify baseline and selected final stage
  const hasBaseline = !!modes['tfidf'];
  const finalKey =
    'rrf-rerank-rewrite' in modes
      ? 'rrf-rerank-rewrite'
      : 'rrf-rerank' in modes
      ? 'rrf-rerank'
      : 'bm25-qdrant-rrf' in modes
      ? 'bm25-qdrant-rrf'
      : modeKeys[modeKeys.length - 1];

  const finalMode = modes[finalKey];
  const baselineHr = hasBaseline ? modes['tfidf']?.hit_rate || 0 : null;
  const delta =
    hasBaseline && finalMode && baselineHr !== null
      ? Math.round(((finalMode.hit_rate || 0) - baselineHr) * 100)
      : null;

  return (
    <div className="card" style={{ marginBottom: '24px' }}>
      <h3
        style={{
          fontSize: '0.84rem',
          fontWeight: 700,
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          color: 'var(--text-primary)',
          margin: '0 0 14px 0',
        }}
      >
        3. Key Takeaways
      </h3>
      <ul style={{ paddingLeft: '20px', display: 'flex', flexDirection: 'column', gap: '8px', margin: 0 }}>
        <li style={{ fontSize: '0.82rem', color: 'var(--text-muted)', lineHeight: 1.55 }}>
          <strong>{best.label}</strong> achieved the highest retrieval rate (
          {Math.round(best.hr * 100)}% Recall@{k}, MRR {best.mrr ? best.mrr.toFixed(3) : '0.000'}).
        </li>

        {delta !== null && baselineHr !== null && finalMode && (
          <li style={{ fontSize: '0.82rem', color: 'var(--text-muted)', lineHeight: 1.55 }}>
            Progression from baseline <strong>TF-IDF</strong> ({Math.round(baselineHr * 100)}%) to selected final stage{' '}
            <strong>{PRESETS[finalKey]?.label || finalKey}</strong> ({Math.round(finalMode.hit_rate * 100)}%) produced a{' '}
            <strong>
              {delta >= 0 ? '+' : ''}
              {delta} percentage point
            </strong>{' '}
            gain.
          </li>
        )}

        <li style={{ fontSize: '0.82rem', color: 'var(--text-muted)', lineHeight: 1.55 }}>
          {hardQ.length > 0 ? (
            <span>
              {hardQ.length} question(s) failed across all active strategies. Consider verifying document chunk
              coverage for missed sections.
            </span>
          ) : (
            <span>All evaluation questions were successfully retrieved within top-{k} by at least one strategy.</span>
          )}
        </li>

        <li style={{ fontSize: '0.82rem', color: 'var(--text-muted)', lineHeight: 1.55 }}>
          Retrieval depth is Top-K = {k}. Both Document Recall and Section Recall are evaluated against candidate chunks.
        </li>
      </ul>
    </div>
  );
};

