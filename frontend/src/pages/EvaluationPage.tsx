import React, { useState, useEffect, useRef } from 'react';
import { EvalQuestionInput, EvalRunResponse } from '../types/evaluation';
import { FormView } from '../components/Evaluation/FormView';
import { ResultsView } from '../components/Evaluation/ResultsView';
import { PRESETS } from '../components/Evaluation/KeyTakeaways';
import { api } from '../services/api';
import { generateId } from '../utils/helpers';

export const EvaluationPage: React.FC = () => {
  const [questions, setQuestions] = useState<EvalQuestionInput[]>([
    { id: generateId('q'), question: '', expected: '' },
    { id: generateId('q'), question: '', expected: '' },
    { id: generateId('q'), question: '', expected: '' },
  ]);
  const [topK, setTopK] = useState<number | string>(8);
  const [strategyFilter, setStrategyFilter] = useState<string>('');
  const [presets, setPresets] = useState<Record<string, boolean>>({
    'tfidf': true,
    'bm25-qdrant-blend': true,
    'bm25-qdrant-rrf': true,
    'rrf-rerank': true,
    'rrf-rerank-rewrite': true,
  });
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [results, setResults] = useState<EvalRunResponse | null>(null);
  const [view, setView] = useState<'form' | 'results'>('form');

  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, [view]);

  const handleCancel = () => {
    const controller = abortControllerRef.current;
    if (controller) {
      controller.abort();
      abortControllerRef.current = null;
      setIsRunning(false);
    }
  };

  const handleRun = async () => {
    // Validate both question AND expected ground truth
    const invalidEmptyExpected = questions.filter((q) => q.question.trim() && !q.expected.trim());
    if (invalidEmptyExpected.length > 0) {
      alert('Please provide an expected section/filename substring for all entered questions.');
      return;
    }

    const validQ = questions.filter((q) => q.question.trim() && q.expected.trim());
    if (!validQ.length) {
      alert('Please enter at least one question and its expected target substring.');
      return;
    }

    const active = Object.keys(presets).filter((k) => presets[k]);
    if (!active.length) {
      alert('Please select at least one retrieval strategy.');
      return;
    }

    const rawTopK = String(topK).trim();
    if (!/^\d+$/.test(rawTopK)) {
      alert('Top-K must be a whole number between 1 and 20.');
      return;
    }
    const kVal = Math.max(1, Math.min(20, Number(rawTopK)));

    setIsRunning(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const data = await api.runEvaluation(
        {
          questions: validQ.map((q) => ({
            id: q.id,
            question: q.question.trim(),
            expected: q.expected.trim(),
          })),
          top_k: kVal,
          presets: active,
          strategy_filter: strategyFilter,
        },
        controller.signal
      );

      // Response schema and result integrity validation
      if (!data || typeof data !== 'object' || !data.modes || typeof data.modes !== 'object') {
        throw new Error('Malformed evaluation response: missing modes dictionary.');
      }

      const submittedIds = new Set(validQ.map((q) => q.id));
      for (const mk of active) {
        const modeData = data.modes[mk];
        if (!modeData || typeof modeData !== 'object' || !Array.isArray(modeData.results)) {
          throw new Error(`Strategy "${PRESETS[mk]?.label || mk}" missing results array in server response.`);
        }

        modeData.hit_rate =
          typeof modeData.hit_rate === 'number' && !isNaN(modeData.hit_rate)
            ? modeData.hit_rate
            : Number(modeData.hit_rate) || 0;
        modeData.mrr =
          typeof modeData.mrr === 'number' && !isNaN(modeData.mrr)
            ? modeData.mrr
            : Number(modeData.mrr) || 0;
        modeData.hits =
          typeof modeData.hits === 'number' && !isNaN(modeData.hits)
            ? modeData.hits
            : Number(modeData.hits) || 0;
        modeData.total =
          typeof modeData.total === 'number' && !isNaN(modeData.total)
            ? modeData.total
            : Number(modeData.total) || 0;

        const resultIds: string[] = [];
        for (const r of modeData.results) {
          if (!r || typeof r !== 'object' || typeof r.id !== 'string') {
            throw new Error(`Strategy "${PRESETS[mk]?.label || mk}" returned an invalid result item structure.`);
          }
          // Strict boolean hit normalization
          if (typeof r.hit === 'boolean') {
            // Valid boolean
          } else if ((r.hit as unknown) === 1 || (r.hit as unknown) === '1' || (r.hit as unknown) === 'true') {
            r.hit = true;
          } else if ((r.hit as unknown) === 0 || (r.hit as unknown) === '0' || (r.hit as unknown) === 'false') {
            r.hit = false;
          } else {
            throw new Error(`Strategy "${PRESETS[mk]?.label || mk}" returned invalid hit value for question ID "${r.id}".`);
          }

          if (r.rank !== null && r.rank !== undefined) {
            const parsedRank = Number(r.rank);
            r.rank = isNaN(parsedRank) || parsedRank <= 0 ? null : Math.floor(parsedRank);
          } else {
            r.rank = null;
          }
          resultIds.push(r.id);
        }

        const uniqueIds = new Set(resultIds);
        if (uniqueIds.size !== resultIds.length) {
          throw new Error(`Strategy "${PRESETS[mk]?.label || mk}" returned duplicate question IDs.`);
        }
        for (const qId of submittedIds) {
          if (!uniqueIds.has(qId)) {
            throw new Error(`Strategy "${PRESETS[mk]?.label || mk}" did not return a result for question ID "${qId}".`);
          }
        }
        for (const resultId of resultIds) {
          if (!submittedIds.has(resultId)) {
            throw new Error(`Strategy "${PRESETS[mk]?.label || mk}" returned unexpected question ID "${resultId}".`);
          }
        }
      }

      setResults(data);
      setView('results');
    } catch (e: unknown) {
      const err = e as Error;
      if (err.name !== 'AbortError') {
        alert('Evaluation Integrity Error: ' + err.message);
      }
    } finally {
      if (abortControllerRef.current === controller) {
        abortControllerRef.current = null;
        setIsRunning(false);
      }
    }
  };

  const goToForm = () => {
    setView('form');
  };

  const goToResults = () => {
    setView('results');
  };

  const handleClear = () => {
    setResults(null);
    setView('form');
  };

  return (
    <div className="eval-root">
      {/* TOPBAR */}
      <header
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 50,
          background: 'var(--bg-surface)',
          borderBottom: '1px solid var(--border)',
          padding: '12px 28px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div>
          <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#fff' }}>Evaluation Results</div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
            Document &amp; Section Recall@K benchmark against indexed documents
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {view === 'form' && results && (
            <button
              type="button"
              onClick={goToResults}
              className="btn-secondary"
              style={{ borderColor: 'var(--accent)', color: 'var(--accent)' }}
            >
              View Results →
            </button>
          )}

          <a href="/" className="btn-secondary">
            ← Back to chat
          </a>
        </div>
      </header>

      {/* MAIN CONTENT */}
      <main style={{ maxWidth: '1000px', width: '100%', margin: '0 auto', padding: '28px 20px 50px 20px', flex: 1 }}>
        {view === 'form' ? (
          <FormView
            questions={questions}
            setQuestions={setQuestions}
            topK={topK}
            setTopK={setTopK}
            strategyFilter={strategyFilter}
            setStrategyFilter={setStrategyFilter}
            presets={presets}
            setPresets={setPresets}
            onRun={handleRun}
            onCancel={handleCancel}
            isRunning={isRunning}
          />
        ) : (
          <ResultsView results={results} onBack={goToForm} onClear={handleClear} />
        )}
      </main>
    </div>
  );
};

