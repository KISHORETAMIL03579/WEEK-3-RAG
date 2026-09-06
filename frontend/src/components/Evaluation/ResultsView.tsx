import React from 'react';
import { EvalRunResponse } from '../../types/evaluation';
import { PRESETS, KeyTakeaways } from './KeyTakeaways';
import { ScoreBadge } from './ScoreBadge';

interface ResultsViewProps {
  results: EvalRunResponse | null;
  onBack: () => void;
  onClear: () => void;
}

export const ResultsView: React.FC<ResultsViewProps> = ({ results, onBack, onClear }) => {
  if (!results || !results.modes) return null;

  const modeKeys = Object.keys(results.modes);
  const firstPreset = results.modes[modeKeys[0]];
  const questionResults = firstPreset && firstPreset.results ? firstPreset.results : [];

  // Pre-build O(1) ID lookup maps per strategy
  const modeMaps: Record<string, Map<string, unknown>> = {};
  modeKeys.forEach((mk) => {
    modeMaps[mk] = new Map((results.modes[mk]?.results || []).map((r) => [r.id, r]));
  });

  // Match cells across modes using stable question IDs
  const qRows = questionResults.map((q) => {
    const qId = q.id;
    return {
      id: qId,
      question: q.question,
      expected: q.expected || q.expected_section || q.expected_doc || '—',
      cells: modeKeys.map((mk) => {
        const match = modeMaps[mk]?.get(qId) as { hit?: boolean; rank?: number | null } | undefined;
        return {
          hit: !!(match && match.hit),
          rank: match ? match.rank : null,
          found: !!match,
        };
      }),
    };
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Top Action Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          Evaluated <strong style={{ color: '#fff' }}>{questionResults.length}</strong> question(s) across{' '}
          <strong style={{ color: '#fff' }}>{modeKeys.length}</strong> retrieval strategy(ies)
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button type="button" onClick={onBack} className="btn-secondary">
            ← Edit Questions
          </button>
          <button type="button" onClick={onClear} className="btn-secondary btn-danger">
            ✕ Clear Results
          </button>
        </div>
      </div>

      {/* 1. OVERALL RESULTS TABLE */}
      <div className="card" style={{ padding: '20px', overflow: 'hidden' }}>
        <h3
          style={{
            fontSize: '0.84rem',
            fontWeight: 700,
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            color: 'var(--text-primary)',
            margin: '0 0 4px 0',
          }}
        >
          1. Overall Results
        </h3>
        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '16px' }}>
          Comparison of Document &amp; Section Recall@K and MRR across ablation stages
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table className="clean-table">
            <caption className="sr-only">Overall retrieval evaluation results across ablation stages</caption>
            <thead>
              <tr>
                <th>Strategy</th>
                <th>{`Recall@${results.k} (Hit-Rate)`}</th>
                <th>MRR</th>
                <th>Passed / Total</th>
              </tr>
            </thead>
            <tbody>
              {modeKeys.map((mk) => {
                const m = results.modes[mk] || { hit_rate: 0, mrr: 0, hits: 0, total: 0 };
                const hitRate = typeof m.hit_rate === 'number' ? m.hit_rate : Number(m.hit_rate || 0);
                const mrrVal = typeof m.mrr === 'number' ? m.mrr : Number(m.mrr || 0);
                const pct = Math.round(hitRate * 100);
                const meta = PRESETS[mk] || { label: mk };
                return (
                  <tr key={mk}>
                    <td style={{ fontWeight: 600, color: '#f3f4f6' }}>{meta.label}</td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <ScoreBadge pct={pct} />
                        <span
                          style={{
                            fontSize: '0.74rem',
                            color: 'var(--text-muted)',
                            fontFamily: 'ui-monospace, monospace',
                          }}
                        >
                          ({m.hits || 0}/{m.total || 0})
                        </span>
                      </div>
                    </td>
                    <td style={{ fontFamily: 'ui-monospace, monospace', color: 'var(--text-primary)', fontWeight: 600 }}>
                      {mrrVal.toFixed(3)}
                    </td>
                    <td style={{ color: 'var(--text-muted)' }}>
                      {m.hits || 0} / {m.total || 0}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* 2. PER-QUESTION MATRIX */}
      <div className="card" style={{ padding: '20px', overflow: 'hidden' }}>
        <h3
          style={{
            fontSize: '0.84rem',
            fontWeight: 700,
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            color: 'var(--text-primary)',
            margin: '0 0 4px 0',
          }}
        >
          2. Per-Question Strategy Matrix
        </h3>
        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '16px' }}>
          Detailed retrieval hit status (and rank position) matched by Question ID
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table className="clean-table" style={{ minWidth: '700px' }}>
            <caption className="sr-only">Per-question retrieval hit status and rank position matrix</caption>
            <thead>
              <tr>
                <th style={{ width: '32px', textAlign: 'center' }}>#</th>
                <th>Question</th>
                <th>Expected Ground Truth</th>
                {modeKeys.map((mk) => {
                  const meta = PRESETS[mk] || { label: mk };
                  return (
                    <th key={mk} style={{ textAlign: 'center', whiteSpace: 'nowrap' }}>
                      {meta.label}
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {qRows.map((row, qi) => (
                <tr key={row.id}>
                  <td
                    style={{
                      textAlign: 'center',
                      color: 'var(--text-muted)',
                      fontFamily: 'ui-monospace, monospace',
                      fontSize: '0.76rem',
                    }}
                  >
                    {qi + 1}
                  </td>
                  <td style={{ fontWeight: 500, color: '#f3f4f6', maxWidth: '280px' }}>{row.question}</td>
                  <td
                    style={{
                      color: 'var(--text-muted)',
                      fontFamily: 'ui-monospace, monospace',
                      fontSize: '0.74rem',
                    }}
                  >
                    {row.expected}
                  </td>
                  {row.cells.map((cell, ci) => (
                    <td key={ci} style={{ textAlign: 'center' }}>
                      {cell.hit ? (
                        <span className="badge-hit">
                          <span>✓</span>
                          <span style={{ fontSize: '0.68rem', color: 'var(--green)' }}>(rank {cell.rank})</span>
                        </span>
                      ) : cell.found ? (
                        <span className="badge-miss">✕</span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>—</span>
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 3. KEY TAKEAWAYS */}
      <KeyTakeaways modes={results.modes} k={results.k} />
    </div>
  );
};

