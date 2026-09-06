import React, { useState, useRef, useEffect } from 'react';
import { EvalQuestionInput } from '../../types/evaluation';
import { PRESETS } from './KeyTakeaways';
import { api } from '../../services/api';
import { generateId } from '../../utils/helpers';

interface FormViewProps {
  questions: EvalQuestionInput[];
  setQuestions: React.Dispatch<React.SetStateAction<EvalQuestionInput[]>>;
  topK: number | string;
  setTopK: (k: number | string) => void;
  strategyFilter: string;
  setStrategyFilter: (s: string) => void;
  presets: Record<string, boolean>;
  setPresets: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
  onRun: () => void;
  onCancel: () => void;
  isRunning: boolean;
}

export const FormView: React.FC<FormViewProps> = ({
  questions,
  setQuestions,
  topK,
  setTopK,
  strategyFilter,
  setStrategyFilter,
  presets,
  setPresets,
  onRun,
  onCancel,
  isRunning,
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isImporting, setIsImporting] = useState(false);
  const importAbortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      if (importAbortRef.current) {
        importAbortRef.current.abort();
      }
    };
  }, []);

  const addQ = () => {
    setQuestions((prev) => [...prev, { id: generateId('q'), question: '', expected: '' }]);
  };

  const updateQ = (id: string, field: 'question' | 'expected', val: string) => {
    setQuestions((prev) => prev.map((q) => (q.id === id ? { ...q, [field]: val } : q)));
  };

  const removeQ = (id: string) => {
    setQuestions((prev) => {
      if (prev.length <= 1) return [{ id: generateId('q'), question: '', expected: '' }];
      return prev.filter((q) => q.id !== id);
    });
  };

  const toggleP = (key: string) => {
    setPresets((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleImport = async () => {
    if (!selectedFile) {
      alert('Please choose a file (.pdf, .txt, .md) first.');
      return;
    }
    if (importAbortRef.current) {
      importAbortRef.current.abort();
    }
    const controller = new AbortController();
    importAbortRef.current = controller;
    setIsImporting(true);

    try {
      const data = await api.parseEvaluationFile(selectedFile, controller.signal);
      if (data.pairs && data.pairs.length) {
        setQuestions(
          data.pairs.map((p) => ({
            id: generateId('q'),
            question: p.question || '',
            expected: p.expected || '',
          }))
        );
      } else {
        alert(data.error || 'No Q/A pairs found in file.');
      }
    } catch (e: unknown) {
      const err = e as Error;
      if (err.name !== 'AbortError') {
        alert('Import error: ' + err.message);
      }
    } finally {
      if (importAbortRef.current === controller) {
        importAbortRef.current = null;
        setIsImporting(false);
      }
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* 1. TEST QUESTIONS */}
      <div className="card">
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '16px',
          }}
        >
          <h2
            style={{
              fontSize: '0.82rem',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              color: 'var(--text-primary)',
              margin: 0,
            }}
          >
            1. Test Questions
          </h2>
          <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
            {questions.filter((q) => q.question.trim() && q.expected.trim()).length} complete / {questions.length} total
          </span>
        </div>

        {/* Import file box */}
        <div
          style={{
            background: 'var(--bg-raised)',
            border: '1px dashed var(--border)',
            borderRadius: '8px',
            padding: '14px 18px',
            marginBottom: '18px',
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '12px',
          }}
        >
          <div>
            <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)' }}>
              Import Q/A Pairs (Optional)
            </div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              Format: one line "Q: question", next line "A: expected section or document substring", blank line between pairs.
            </div>
          </div>

          <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
            <input
              id="qa-file-upload"
              type="file"
              accept=".pdf,.txt,.md"
              style={{ display: 'none' }}
              onChange={(e) => {
                if (e.target.files && e.target.files[0]) {
                  setSelectedFile(e.target.files[0]);
                }
              }}
            />

            <button
              type="button"
              onClick={() => {
                document.getElementById('qa-file-upload')?.click();
              }}
              className="btn-secondary"
              style={{ padding: '6px 12px' }}
            >
              <span>📁</span>
              <span>{selectedFile ? 'Change File' : 'Choose File'}</span>
            </button>

            {selectedFile ? (
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  background: 'var(--accent-dim)',
                  border: '1px solid var(--accent-border)',
                  padding: '3px 6px 3px 10px',
                  borderRadius: '6px',
                }}
              >
                <span
                  style={{
                    fontSize: '0.75rem',
                    color: 'var(--text-primary)',
                    fontFamily: 'ui-monospace, monospace',
                    maxWidth: '180px',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {selectedFile.name}
                </span>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedFile(null);
                    const fileInput = document.getElementById('qa-file-upload') as HTMLInputElement | null;
                    if (fileInput) fileInput.value = '';
                  }}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'var(--text-muted)',
                    cursor: 'pointer',
                    padding: '2px 5px',
                    borderRadius: '4px',
                    fontSize: '0.8rem',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    lineHeight: 1,
                  }}
                  title="Remove selected file"
                >
                  ✕
                </button>
              </div>
            ) : (
              <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>No file chosen</span>
            )}

            <button
              type="button"
              onClick={handleImport}
              disabled={isImporting || !selectedFile}
              className="btn-primary"
              style={{
                padding: '6px 14px',
                fontSize: '0.78rem',
                opacity: selectedFile ? 1 : 0.45,
              }}
            >
              {isImporting ? 'Importing...' : 'Import'}
            </button>
          </div>
        </div>

        {/* Question Rows */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {questions.map((q, idx) => (
            <div key={q.id} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <span
                style={{
                  fontSize: '0.72rem',
                  color: 'var(--text-muted)',
                  width: '22px',
                  textAlign: 'center',
                  fontFamily: 'ui-monospace, monospace',
                }}
              >
                {idx + 1}
              </span>
              <input
                type="text"
                placeholder="Question"
                value={q.question}
                onChange={(e) => updateQ(q.id, 'question', e.target.value)}
                className="input-field"
                style={{ flex: 2 }}
              />
              <input
                type="text"
                placeholder="Expected section or document substring (e.g. Leave Policy or HRPolicy.pdf)"
                value={q.expected}
                onChange={(e) => updateQ(q.id, 'expected', e.target.value)}
                className="input-field"
                style={{ flex: 1.4, fontFamily: 'ui-monospace, monospace', fontSize: '0.8rem' }}
              />
              <button
                type="button"
                onClick={() => removeQ(q.id)}
                style={{
                  background: 'none',
                  border: '1px solid var(--border)',
                  color: 'var(--text-muted)',
                  borderRadius: '6px',
                  width: '34px',
                  height: '34px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.85rem',
                }}
                title="Remove"
              >
                ✕
              </button>
            </div>
          ))}
        </div>

        <button type="button" onClick={addQ} className="btn-secondary" style={{ marginTop: '12px' }}>
          + Add question
        </button>
      </div>

      {/* 2. SETTINGS */}
      <div className="card">
        <h2
          style={{
            fontSize: '0.82rem',
            fontWeight: 700,
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            color: 'var(--text-primary)',
            margin: '0 0 16px 0',
          }}
        >
          2. Settings
        </h2>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '16px',
            marginBottom: '18px',
          }}
        >
          <div>
            <label
              htmlFor="top-k-stepper-input"
              style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '6px' }}
            >
              Top-k
            </label>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                background: 'var(--bg-raised)',
                border: '1px solid var(--border)',
                borderRadius: '8px',
                overflow: 'hidden',
                height: '38px',
              }}
            >
              <button
                type="button"
                onClick={() => {
                  const current = parseInt(String(topK), 10) || 1;
                  setTopK(Math.max(1, current - 1));
                }}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--text-muted)',
                  width: '36px',
                  height: '100%',
                  cursor: 'pointer',
                  fontSize: '1.1rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
                title="Decrease Top-k"
              >
                −
              </button>
              <input
                id="top-k-stepper-input"
                type="number"
                min="1"
                max="20"
                step="1"
                value={topK}
                onChange={(e) => {
                  const raw = e.target.value;
                  if (raw === '') {
                    setTopK('');
                  } else {
                    const val = parseInt(raw, 10);
                    if (!isNaN(val)) {
                      setTopK(Math.max(1, Math.min(20, val)));
                    }
                  }
                }}
                onBlur={() => {
                  const trimmed = String(topK).trim();
                  if (!/^\d+$/.test(trimmed)) {
                    setTopK(8);
                    return;
                  }
                  const val = Number(trimmed);
                  setTopK(Math.max(1, Math.min(20, val)));
                }}
                style={{
                  flex: 1,
                  textAlign: 'center',
                  background: 'transparent',
                  border: 'none',
                  color: '#fff',
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  outline: 'none',
                  padding: 0,
                }}
              />
              <button
                type="button"
                onClick={() => {
                  const current = parseInt(String(topK), 10) || 1;
                  setTopK(Math.min(20, current + 1));
                }}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--text-muted)',
                  width: '36px',
                  height: '100%',
                  cursor: 'pointer',
                  fontSize: '1.1rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
                title="Increase Top-k"
              >
                +
              </button>
            </div>
          </div>
          <div>
            <label
              htmlFor="strategy-filter-input"
              style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '6px' }}
            >
              Chunk strategy filter (optional)
            </label>
            <input
              id="strategy-filter-input"
              type="text"
              placeholder="e.g. structured — leave blank for all"
              value={strategyFilter}
              onChange={(e) => setStrategyFilter(e.target.value)}
              className="input-field"
              style={{ width: '100%' }}
            />
          </div>
        </div>

        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '10px', fontWeight: 600 }}>
          Ablation stages to compare
        </div>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '10px',
            marginBottom: '22px',
          }}
        >
          {Object.keys(PRESETS).map((key) => {
            const meta = PRESETS[key];
            const isChecked = !!presets[key];
            return (
              <label key={key} className={`stage-checkbox ${isChecked ? 'checked' : ''}`}>
                <input
                  type="checkbox"
                  checked={isChecked}
                  onChange={() => toggleP(key)}
                  style={{ accentColor: 'var(--accent)', width: '15px', height: '15px', cursor: 'pointer' }}
                />
                <div>
                  <div style={{ fontSize: '0.8rem', fontWeight: 600, color: isChecked ? '#fff' : 'var(--text-muted)' }}>
                    {meta.label}
                  </div>
                  <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: '1px' }}>
                    {meta.desc}
                  </div>
                </div>
              </label>
            );
          })}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button type="button" onClick={onRun} disabled={isRunning} className="btn-primary">
            {isRunning ? 'Running evaluation...' : 'Run evaluation'}
          </button>

          {isRunning && (
            <button type="button" onClick={onCancel} className="btn-secondary btn-danger">
              Cancel
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

