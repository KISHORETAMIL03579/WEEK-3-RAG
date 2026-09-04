// Professional, clean enterprise stylesheet
(function () {
  var s = document.createElement('style');
  s.textContent = [
    ':root {',
    '  --bg: #0b0f19;',
    '  --surface: #111827;',
    '  --surface-raised: #1f2937;',
    '  --border: #1f293d;',
    '  --border-subtle: rgba(255, 255, 255, 0.07);',
    '  --primary: #3b82f6;',
    '  --primary-hover: #2563eb;',
    '  --text: #f3f4f6;',
    '  --text-muted: #9ca3af;',
    '  --text-subtle: #6b7280;',
    '  --green-bg: rgba(16, 185, 129, 0.12);',
    '  --green-text: #10b981;',
    '  --green-border: rgba(16, 185, 129, 0.25);',
    '  --red-bg: rgba(239, 68, 68, 0.12);',
    '  --red-text: #ef4444;',
    '  --red-border: rgba(239, 68, 68, 0.25);',
    '  --amber-bg: rgba(245, 158, 11, 0.12);',
    '  --amber-text: #f59e0b;',
    '  --amber-border: rgba(245, 158, 11, 0.25);',
    '}',
    'html { height: auto !important; overflow-y: scroll !important; overflow-x: hidden !important; scroll-behavior: smooth; background: var(--bg); scrollbar-width: thin; scrollbar-color: rgba(148, 163, 184, 0.25) transparent; }',
    'body { height: auto !important; min-height: 100vh !important; overflow: visible !important; background: var(--bg); font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color: var(--text); margin: 0; }',
    '#root { min-height: 100vh; display: flex; flex-direction: column; }',
    '::-webkit-scrollbar { width: 6px; height: 6px; }',
    '::-webkit-scrollbar-track { background: transparent; }',
    '::-webkit-scrollbar-thumb { background: rgba(148, 163, 184, 0.22); border-radius: 9999px; transition: background 0.2s ease; }',
    '::-webkit-scrollbar-thumb:hover { background: rgba(148, 163, 184, 0.45); }',
    '.card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 24px; }',
    '.input-field { background: var(--surface-raised); border: 1px solid var(--border); border-radius: 8px; padding: 9px 12px; font-size: 0.83rem; color: #fff; outline: none; transition: border-color 0.15s ease; }',
    '.input-field:focus { border-color: var(--primary); }',
    '.btn-primary { background: var(--primary); color: #fff; font-weight: 600; font-size: 0.84rem; border-radius: 8px; border: none; padding: 10px 22px; cursor: pointer; transition: background 0.15s ease; display: inline-flex; align-items: center; justify-content: center; gap: 8px; }',
    '.btn-primary:hover:not(:disabled) { background: var(--primary-hover); }',
    '.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }',
    '.btn-secondary { background: var(--surface-raised); border: 1px solid var(--border); color: var(--text); padding: 7px 14px; border-radius: 8px; font-size: 0.78rem; font-weight: 500; cursor: pointer; transition: all 0.15s ease; text-decoration: none; display: inline-flex; align-items: center; gap: 6px; }',
    '.btn-secondary:hover { background: #374151; border-color: #4b5563; }',
    '.btn-danger { color: #f87171; border-color: rgba(239, 68, 68, 0.3); }',
    '.btn-danger:hover { background: rgba(239, 68, 68, 0.15); border-color: #ef4444; color: #fff; }',
    '.stage-checkbox { display: flex; align-items: center; gap: 10px; padding: 10px 14px; border-radius: 8px; border: 1px solid var(--border); background: var(--surface-raised); cursor: pointer; transition: all 0.15s ease; user-select: none; }',
    '.stage-checkbox:hover { border-color: #4b5563; }',
    '.stage-checkbox.checked { border-color: rgba(59, 130, 246, 0.5); background: rgba(59, 130, 246, 0.08); }',
    '.clean-table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }',
    '.clean-table th { text-align: left; padding: 12px 14px; color: var(--text-muted); font-weight: 600; font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.04em; border-bottom: 1px solid var(--border); background: rgba(17, 24, 39, 0.7); }',
    '.clean-table td { padding: 12px 14px; border-bottom: 1px solid var(--border-subtle); }',
    '.clean-table tr:hover td { background: rgba(255, 255, 255, 0.015); }',
    '.badge-hit { display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; border-radius: 6px; background: var(--green-bg); border: 1px solid var(--green-border); color: var(--green-text); font-weight: 600; font-size: 0.74rem; }',
    '.badge-miss { display: inline-flex; align-items: center; justify-content: center; width: 22px; height: 22px; border-radius: 5px; background: var(--red-bg); border: 1px solid var(--red-border); color: var(--red-text); font-weight: 700; font-size: 0.8rem; }',
    '.score-pill { display: inline-flex; align-items: center; padding: 3px 8px; border-radius: 6px; font-weight: 700; font-family: ui-monospace, monospace; font-size: 0.78rem; }',
    'input[type=number]::-webkit-inner-spin-button, input[type=number]::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }',
    'input[type=number] { -moz-appearance: textfield; }'
  ].join('\n');
  document.head.appendChild(s);
}());

const { useState, useRef } = React;

function generateId() {
  return 'q_' + Math.random().toString(36).substring(2, 11);
}

const PRESETS = {
  'tfidf':              { label: 'TF-IDF baseline',              desc: 'Sparse keyword matching' },
  'bm25-qdrant-blend':  { label: 'BM25 + Qdrant (Weighted Blend)', desc: 'Hybrid dense/sparse blend' },
  'bm25-qdrant-rrf':    { label: 'BM25 + Qdrant (RRF)',          desc: 'Reciprocal rank fusion' },
  'rrf-rerank':         { label: '+ Cross-Encoder Rerank',       desc: 'Contextual reranking' },
  'rrf-rerank-rewrite': { label: '+ Query Rewriting',            desc: 'Subquery expansion & rewrite' },
};

/* ── Score Badge ─────────────────────────────────────────────────── */
function ScoreBadge({ pct }) {
  let style = { background: 'var(--red-bg)', border: '1px solid var(--red-border)', color: 'var(--red-text)' };
  if (pct >= 80) {
    style = { background: 'var(--green-bg)', border: '1px solid var(--green-border)', color: 'var(--green-text)' };
  } else if (pct >= 50) {
    style = { background: 'var(--amber-bg)', border: '1px solid var(--amber-border)', color: 'var(--amber-text)' };
  }
  return (
    <span className="score-pill" style={style}>
      {pct}%
    </span>
  );
}

/* ── Key Takeaways (Safe React Node Rendering with MRR Tie-Breaking) ── */
function KeyTakeaways({ modes, k }) {
  const modeKeys = Object.keys(modes || {});
  if (!modeKeys.length) return null;

  const rows = modeKeys.map(function(key) {
    const meta = PRESETS[key] || { label: key };
    return { key, label: meta.label, hr: modes[key].hit_rate || 0, mrr: modes[key].mrr || 0 };
  });

  // SR-04: Best strategy determined by highest Hit-Rate, with MRR as decisive tie-breaker
  const best = rows.reduce(function(a, b) {
    if (b.hr !== a.hr) return b.hr > a.hr ? b : a;
    if (b.mrr !== a.mrr) return b.mrr > a.mrr ? b : a;
    return a;
  }, rows[0]);

  const firstResults = (modes[modeKeys[0]] && modes[modeKeys[0]].results) ? modes[modeKeys[0]].results : [];
  const hardQ = firstResults.filter(function(_, qi) {
    return modeKeys.every(function(mk) { return !(modes[mk].results[qi] && modes[mk].results[qi].hit); });
  });

  // SR-05: Explicitly identify baseline and selected final stage
  const hasBaseline = !!modes['tfidf'];
  const finalKey = 'rrf-rerank-rewrite' in modes
    ? 'rrf-rerank-rewrite'
    : ('rrf-rerank' in modes ? 'rrf-rerank' : ('bm25-qdrant-rrf' in modes ? 'bm25-qdrant-rrf' : modeKeys[modeKeys.length - 1]));
  
  const finalMode = modes[finalKey];
  const baselineHr = hasBaseline ? (modes['tfidf'].hit_rate || 0) : null;
  const delta = (hasBaseline && finalMode) ? Math.round(((finalMode.hit_rate || 0) - baselineHr) * 100) : null;

  return (
    <div className="card" style={{ marginBottom: '24px' }}>
      <h3 style={{ fontSize: '0.84rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text)', margin: '0 0 14px 0' }}>
        3. Key Takeaways
      </h3>
      <ul style={{ paddingLeft: '20px', display: 'flex', flexDirection: 'column', gap: '8px', margin: 0 }}>
        <li style={{ fontSize: '0.82rem', color: 'var(--text-muted)', lineHeight: 1.55 }}>
          <strong>{best.label}</strong> achieved the highest retrieval rate ({Math.round(best.hr * 100)}% Recall@{k}, MRR {best.mrr ? best.mrr.toFixed(3) : '0.000'}).
        </li>

        {delta !== null && (
          <li style={{ fontSize: '0.82rem', color: 'var(--text-muted)', lineHeight: 1.55 }}>
            Progression from baseline <strong>TF-IDF</strong> ({Math.round(baselineHr * 100)}%) to selected final stage <strong>{PRESETS[finalKey]?.label || finalKey}</strong> ({Math.round(finalMode.hit_rate * 100)}%) produced a <strong>{delta >= 0 ? '+' : ''}{delta} percentage point</strong> gain.
          </li>
        )}

        <li style={{ fontSize: '0.82rem', color: 'var(--text-muted)', lineHeight: 1.55 }}>
          {hardQ.length > 0 ? (
            <span>
              {hardQ.length} question(s) failed across all active strategies. Consider verifying document chunk coverage for missed sections.
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
}

/* ── FORM VIEW ────────────────────────────────────────────────────── */
function FormView({ questions, setQuestions, topK, setTopK, strategyFilter, setStrategyFilter,
                    presets, setPresets, onRun, onCancel, isRunning, hasResults, onGoToResults }) {

  const [selectedFile, setSelectedFile] = useState(null);
  const [isImporting, setIsImporting]   = useState(false);

  const addQ = function() {
    setQuestions(prev => [...prev, { id: generateId(), question: '', expected: '' }]);
  };

  const updateQ = function(id, field, val) {
    setQuestions(prev => prev.map(q => q.id === id ? { ...q, [field]: val } : q));
  };

  const removeQ = function(id) {
    setQuestions(prev => {
      if (prev.length <= 1) return [{ id: generateId(), question: '', expected: '' }];
      return prev.filter(q => q.id !== id);
    });
  };

  const toggleP = function(key) {
    setPresets(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const handleImport = async function() {
    if (!selectedFile) { alert('Please choose a file (.pdf, .txt, .md) first.'); return; }
    setIsImporting(true);
    const fd = new FormData();
    fd.append('file', selectedFile);
    try {
      const res  = await fetch('/eval/parse-qa-pdf', { method: 'POST', body: fd });
      const contentType = res.headers.get('content-type') || '';
      let data;
      if (contentType.includes('application/json')) {
        data = await res.json();
      } else {
        const text = await res.text();
        throw new Error(text || `Server error (HTTP ${res.status})`);
      }

      if (res.ok && data.pairs && data.pairs.length) {
        setQuestions(data.pairs.map(p => ({ id: generateId(), question: p.question || '', expected: p.expected || '' })));
      } else {
        alert(data.error || 'No Q/A pairs found in file.');
      }
    } catch(e) {
      alert('Import error: ' + e.message);
    } finally {
      setIsImporting(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

      {/* 1. TEST QUESTIONS */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h2 style={{ fontSize: '0.82rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text)', margin: 0 }}>
            1. Test Questions
          </h2>
          <span style={{ fontSize: '0.74rem', color: 'var(--text-subtle)' }}>
            {questions.filter(q => q.question.trim() && q.expected.trim()).length} complete / {questions.length} total
          </span>
        </div>

        {/* Import file box */}
        <div style={{
          background: 'var(--surface-raised)',
          border: '1px dashed var(--border)',
          borderRadius: '8px',
          padding: '14px 18px',
          marginBottom: '18px',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '12px'
        }}>
          <div>
            <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text)' }}>
              Import Q/A Pairs (Optional)
            </div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-subtle)', marginTop: '2px' }}>
              Format: one line "Q: question", next line "A: expected section or document substring", blank line between pairs.
            </div>
          </div>

          <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
            <input
              id="qa-file-upload"
              type="file"
              accept=".pdf,.txt,.md"
              style={{ display: 'none' }}
              onChange={function(e) {
                if (e.target.files && e.target.files[0]) {
                  setSelectedFile(e.target.files[0]);
                }
              }}
            />

            <button
              type="button"
              onClick={function() { document.getElementById('qa-file-upload').click(); }}
              className="btn-secondary"
              style={{ padding: '6px 12px' }}
            >
              <span>📁</span>
              <span>{selectedFile ? 'Change File' : 'Choose File'}</span>
            </button>

            {selectedFile ? (
              <div style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                background: 'rgba(59, 130, 246, 0.12)',
                border: '1px solid rgba(59, 130, 246, 0.3)',
                padding: '3px 6px 3px 10px',
                borderRadius: '6px'
              }}>
                <span style={{
                  fontSize: '0.75rem',
                  color: 'var(--text)',
                  fontFamily: 'ui-monospace, monospace',
                  maxWidth: '180px',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap'
                }}>
                  {selectedFile.name}
                </span>
                <button
                  type="button"
                  onClick={function(e) {
                    e.stopPropagation();
                    setSelectedFile(null);
                    const fileInput = document.getElementById('qa-file-upload');
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
                    transition: 'color 0.15s ease'
                  }}
                  onMouseOver={function(e) { e.currentTarget.style.color = '#ef4444'; }}
                  onMouseOut={function(e) { e.currentTarget.style.color = 'var(--text-muted)'; }}
                  title="Remove selected file"
                >
                  ✕
                </button>
              </div>
            ) : (
              <span style={{ fontSize: '0.74rem', color: 'var(--text-subtle)' }}>
                No file chosen
              </span>
            )}

            <button
              type="button"
              onClick={handleImport}
              disabled={isImporting || !selectedFile}
              className="btn-primary"
              style={{
                padding: '6px 14px',
                fontSize: '0.78rem',
                opacity: selectedFile ? 1 : 0.45
              }}
            >
              {isImporting ? 'Importing...' : 'Import'}
            </button>
          </div>
        </div>

        {/* Question Rows */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {questions.map(function(q, idx) {
            return (
              <div key={q.id} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-subtle)', width: '22px', textAlign: 'center', fontFamily: 'ui-monospace, monospace' }}>
                  {idx + 1}
                </span>
                <input
                  type="text"
                  placeholder="Question"
                  value={q.question}
                  onChange={function(e) { updateQ(q.id, 'question', e.target.value); }}
                  className="input-field"
                  style={{ flex: 2 }}
                />
                <input
                  type="text"
                  placeholder="Expected section or document substring (e.g. Leave Policy or HRPolicy.pdf)"
                  value={q.expected}
                  onChange={function(e) { updateQ(q.id, 'expected', e.target.value); }}
                  className="input-field"
                  style={{ flex: 1.4, fontFamily: 'ui-monospace, monospace', fontSize: '0.8rem' }}
                />
                <button
                  type="button"
                  onClick={function() { removeQ(q.id); }}
                  style={{
                    background: 'none',
                    border: '1px solid var(--border)',
                    color: 'var(--text-subtle)',
                    borderRadius: '6px',
                    width: '34px',
                    height: '34px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '0.85rem'
                  }}
                  title="Remove"
                >
                  ✕
                </button>
              </div>
            );
          })}
        </div>

        <button
          type="button"
          onClick={addQ}
          className="btn-secondary"
          style={{ marginTop: '12px' }}
        >
          + Add question
        </button>
      </div>

      {/* 2. SETTINGS */}
      <div className="card">
        <h2 style={{ fontSize: '0.82rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text)', margin: '0 0 16px 0' }}>
          2. Settings
        </h2>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', marginBottom: '18px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '6px' }}>
              Top-k
            </label>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              background: 'var(--surface-raised)',
              border: '1px solid var(--border)',
              borderRadius: '8px',
              overflow: 'hidden',
              height: '38px'
            }}>
              <button
                type="button"
                onClick={function() {
                  const current = parseInt(topK, 10) || 1;
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
                  transition: 'all 0.15s ease'
                }}
                title="Decrease Top-k"
              >
                −
              </button>
              <input
                type="number"
                min="1"
                max="20"
                step="1"
                value={topK}
                onChange={function(e) {
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
                onBlur={function() {
                  if (!topK || parseInt(topK, 10) < 1) {
                    setTopK(1);
                  }
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
                  padding: 0
                }}
              />
              <button
                type="button"
                onClick={function() {
                  const current = parseInt(topK, 10) || 1;
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
                  transition: 'all 0.15s ease'
                }}
                title="Increase Top-k"
              >
                +
              </button>
            </div>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '6px' }}>
              Chunk strategy filter (optional)
            </label>
            <input
              type="text"
              placeholder="e.g. structured — leave blank for all"
              value={strategyFilter}
              onChange={function(e) { setStrategyFilter(e.target.value); }}
              className="input-field"
              style={{ width: '100%' }}
            />
          </div>
        </div>

        <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '10px' }}>
          Ablation stages to compare
        </label>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '10px', marginBottom: '22px' }}>
          {Object.keys(PRESETS).map(function(key) {
            const meta = PRESETS[key];
            const isChecked = !!presets[key];
            return (
              <label
                key={key}
                className={'stage-checkbox ' + (isChecked ? 'checked' : '')}
              >
                <input
                  type="checkbox"
                  checked={isChecked}
                  onChange={function() { toggleP(key); }}
                  style={{ accentColor: 'var(--primary)', width: '15px', height: '15px', cursor: 'pointer' }}
                />
                <div>
                  <div style={{ fontSize: '0.8rem', fontWeight: 600, color: isChecked ? '#fff' : 'var(--text-muted)' }}>
                    {meta.label}
                  </div>
                  <div style={{ fontSize: '0.68rem', color: 'var(--text-subtle)', marginTop: '1px' }}>
                    {meta.desc}
                  </div>
                </div>
              </label>
            );
          })}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            type="button"
            onClick={onRun}
            disabled={isRunning}
            className="btn-primary"
          >
            {isRunning ? 'Running evaluation...' : 'Run evaluation'}
          </button>

          {isRunning && (
            <button
              type="button"
              onClick={onCancel}
              className="btn-secondary btn-danger"
            >
              Cancel
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── RESULTS VIEW ─────────────────────────────────────────────────── */
function ResultsView({ results, onBack, onClear }) {
  if (!results || !results.modes) return null;

  const modeKeys = Object.keys(results.modes);
  const firstPreset = results.modes[modeKeys[0]];
  const questionResults = firstPreset && firstPreset.results ? firstPreset.results : [];

  // SR-09: Pre-build O(1) ID lookup maps per strategy
  const modeMaps = {};
  modeKeys.forEach(function(mk) {
    modeMaps[mk] = new Map((results.modes[mk]?.results || []).map(function(r) { return [r.id, r]; }));
  });

  // Match cells across modes using stable question IDs
  const qRows = questionResults.map(function(q) {
    const qId = q.id;
    return {
      id: qId,
      question: q.question,
      expected: q.expected || q.expected_section || q.expected_doc || '—',
      cells: modeKeys.map(function(mk) {
        const match = modeMaps[mk] ? modeMaps[mk].get(qId) : null;
        return {
          hit: !!(match && match.hit),
          rank: match ? match.rank : null,
          found: !!match
        };
      })
    };
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

      {/* Top Action Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          Evaluated <strong style={{ color: '#fff' }}>{questionResults.length}</strong> question(s) across <strong style={{ color: '#fff' }}>{modeKeys.length}</strong> retrieval strategy(ies)
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
        <h3 style={{ fontSize: '0.84rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text)', margin: '0 0 4px 0' }}>
          1. Overall Results
        </h3>
        <div style={{ fontSize: '0.72rem', color: 'var(--text-subtle)', marginBottom: '16px' }}>
          Comparison of Document &amp; Section Recall@K and MRR across ablation stages
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table className="clean-table">
            <thead>
              <tr>
                <th>Strategy</th>
                <th>{'Recall@' + results.k + ' (Hit-Rate)'}</th>
                <th>MRR</th>
                <th>Passed / Total</th>
              </tr>
            </thead>
            <tbody>
              {modeKeys.map(function(mk) {
                const m = results.modes[mk];
                const pct = Math.round((m.hit_rate || 0) * 100);
                const meta = PRESETS[mk] || { label: mk };
                return (
                  <tr key={mk}>
                    <td style={{ fontWeight: 600, color: '#f3f4f6' }}>
                      {meta.label}
                    </td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <ScoreBadge pct={pct} />
                        <span style={{ fontSize: '0.74rem', color: 'var(--text-subtle)', fontFamily: 'ui-monospace, monospace' }}>
                          ({m.hits}/{m.total})
                        </span>
                      </div>
                    </td>
                    <td style={{ fontFamily: 'ui-monospace, monospace', color: 'var(--text)', fontWeight: 600 }}>
                      {m.mrr ? m.mrr.toFixed(3) : '0.000'}
                    </td>
                    <td style={{ color: 'var(--text-muted)' }}>
                      {m.hits} / {m.total}
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
        <h3 style={{ fontSize: '0.84rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text)', margin: '0 0 4px 0' }}>
          2. Per-Question Strategy Matrix
        </h3>
        <div style={{ fontSize: '0.72rem', color: 'var(--text-subtle)', marginBottom: '16px' }}>
          Detailed retrieval hit status (and rank position) matched by Question ID
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table className="clean-table" style={{ minWidth: '700px' }}>
            <thead>
              <tr>
                <th style={{ width: '32px', textAlign: 'center' }}>#</th>
                <th>Question</th>
                <th>Expected Ground Truth</th>
                {modeKeys.map(function(mk) {
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
              {qRows.map(function(row, qi) {
                return (
                  <tr key={row.id}>
                    <td style={{ textAlign: 'center', color: 'var(--text-subtle)', fontFamily: 'ui-monospace, monospace', fontSize: '0.76rem' }}>
                      {qi + 1}
                    </td>
                    <td style={{ fontWeight: 500, color: '#f3f4f6', maxWidth: '280px' }}>
                      {row.question}
                    </td>
                    <td style={{ color: 'var(--text-muted)', fontFamily: 'ui-monospace, monospace', fontSize: '0.74rem' }}>
                      {row.expected}
                    </td>
                    {row.cells.map(function(cell, ci) {
                      return (
                        <td key={ci} style={{ textAlign: 'center' }}>
                          {cell.hit ? (
                            <span className="badge-hit">
                              <span>✓</span>
                              <span style={{ fontSize: '0.68rem', color: 'var(--green-text)' }}>(rank {cell.rank})</span>
                            </span>
                          ) : cell.found ? (
                            <span className="badge-miss">✕</span>
                          ) : (
                            <span style={{ color: 'var(--text-subtle)', fontSize: '0.7rem' }}>—</span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* 3. KEY TAKEAWAYS */}
      <KeyTakeaways modes={results.modes} k={results.k} />
    </div>
  );
}

/* ── ROOT APP ─────────────────────────────────────────────────────── */
function EvalApp() {
  const [questions, setQuestions] = useState([
    { id: generateId(), question: '', expected: '' },
    { id: generateId(), question: '', expected: '' },
    { id: generateId(), question: '', expected: '' },
  ]);
  const [topK, setTopK]                     = useState(3);
  const [strategyFilter, setStrategyFilter] = useState('');
  const [presets, setPresets]               = useState({
    'tfidf': true,
    'bm25-qdrant-blend': true,
    'bm25-qdrant-rrf': true,
    'rrf-rerank': true,
    'rrf-rerank-rewrite': true
  });
  const [isRunning, setIsRunning] = useState(false);
  const [results, setResults]     = useState(null);
  const [view, setView]           = useState('form');

  const abortControllerRef = useRef(null);

  const handleCancel = function() {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsRunning(false);
  };

  const handleRun = async function() {
    // Validate both question AND expected ground truth
    const invalidEmptyExpected = questions.filter(function(q) {
      return q.question.trim() && !q.expected.trim();
    });
    if (invalidEmptyExpected.length > 0) {
      alert('Please provide an expected section/filename substring for all entered questions.');
      return;
    }

    const validQ = questions.filter(function(q) {
      return q.question.trim() && q.expected.trim();
    });
    if (!validQ.length) {
      alert('Please enter at least one question and its expected target substring.');
      return;
    }

    const active = Object.keys(presets).filter(function(k) { return presets[k]; });
    if (!active.length) {
      alert('Please select at least one retrieval strategy.');
      return;
    }

    setIsRunning(true);
    const kVal = Math.max(1, Math.min(20, parseInt(topK, 10) || 3));

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const res = await fetch('/eval/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
        body: JSON.stringify({
          questions: validQ.map(q => ({
            id: q.id,
            question: q.question.trim(),
            expected: q.expected.trim()
          })),
          top_k: kVal,
          presets: active,
          strategy_filter: strategyFilter
        })
      });

      const contentType = res.headers.get('content-type') || '';
      let data;
      if (contentType.includes('application/json')) {
        data = await res.json();
      } else {
        const text = await res.text();
        throw new Error(text || `Server returned error (HTTP ${res.status})`);
      }

      if (!res.ok) {
        alert(data.error || 'Evaluation execution failed');
        return;
      }

      // SR-03 & SR-06: Response schema and result integrity validation
      if (!data || typeof data !== 'object' || !data.modes) {
        throw new Error('Malformed evaluation response: missing modes dictionary.');
      }

      const submittedIds = new Set(validQ.map(q => q.id));
      for (const mk of active) {
        const modeData = data.modes[mk];
        if (!modeData || !Array.isArray(modeData.results)) {
          throw new Error(`Strategy "${PRESETS[mk]?.label || mk}" missing results array in server response.`);
        }
        const resultIds = modeData.results.map(r => r.id);
        const uniqueIds = new Set(resultIds);
        if (uniqueIds.size !== resultIds.length) {
          throw new Error(`Strategy "${PRESETS[mk]?.label || mk}" returned duplicate question IDs.`);
        }
        for (const qId of submittedIds) {
          if (!uniqueIds.has(qId)) {
            throw new Error(`Strategy "${PRESETS[mk]?.label || mk}" did not return a result for question ID "${qId}".`);
          }
        }
      }

      setResults(data);
      setView('results');
      setTimeout(function() { window.scrollTo({ top: 0, behavior: 'smooth' }); }, 80);

    } catch(e) {
      if (e.name === 'AbortError') {
        // User cancelled intentionally
      } else {
        alert('Evaluation Integrity Error: ' + e.message);
      }
    } finally {
      setIsRunning(false);
      abortControllerRef.current = null;
    }
  };

  const goToForm = function() {
    setView('form');
    setTimeout(function() { window.scrollTo({ top: 0, behavior: 'smooth' }); }, 50);
  };

  const goToResults = function() {
    setView('results');
    setTimeout(function() { window.scrollTo({ top: 0, behavior: 'smooth' }); }, 50);
  };

  const handleClear = function() {
    setResults(null);
    setView('form');
    setTimeout(function() { window.scrollTo({ top: 0, behavior: 'smooth' }); }, 50);
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>

      {/* TOPBAR */}
      <header style={{
        position: 'sticky',
        top: 0,
        zIndex: 50,
        background: 'var(--surface)',
        borderBottom: '1px solid var(--border)',
        padding: '12px 28px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between'
      }}>
        <div>
          <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#fff' }}>
            Evaluation Results
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-subtle)' }}>
            Document &amp; Section Recall@K benchmark against indexed documents
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {view === 'form' && results && (
            <button type="button" onClick={goToResults} className="btn-secondary" style={{ borderColor: 'var(--primary)', color: 'var(--primary)' }}>
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
            hasResults={!!results}
            onGoToResults={goToResults}
          />
        ) : (
          <ResultsView
            results={results}
            onBack={goToForm}
            onClear={handleClear}
          />
        )}
      </main>
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<EvalApp />);
