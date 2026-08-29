const { useState } = React;

function EvalApp() {
  const [questions, setQuestions] = useState([
    { question: '', expected: '' },
    { question: '', expected: '' },
    { question: '', expected: '' }
  ]);
  const [topK, setTopK] = useState(3);
  const [strategyFilter, setStrategyFilter] = useState('');
  const [presets, setPresets] = useState({
    'tfidf': true,
    'bm25-qdrant-blend': false,
    'bm25-qdrant-rrf': true,
    'rrf-rerank': false,
    'rrf-rerank-rewrite': false
  });
  const [isRunning, setIsRunning] = useState(false);
  const [results, setResults] = useState(null);

  const addQuestion = () => {
    setQuestions([...questions, { question: '', expected: '' }]);
  };

  const updateQuestion = (idx, field, val) => {
    const next = [...questions];
    next[idx][field] = val;
    setQuestions(next);
  };

  const removeQuestion = (idx) => {
    setQuestions(questions.filter((_, i) => i !== idx));
  };

  const togglePreset = (key) => {
    setPresets({ ...presets, [key]: !presets[key] });
  };

  const runEval = async () => {
    setIsRunning(true);
    setResults(null);

    const activePresets = Object.keys(presets).filter((k) => presets[k]);
    const validQuestions = questions.filter((q) => q.question.trim());

    try {
      const res = await fetch('/eval/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          questions: validQuestions,
          top_k: parseInt(topK, 10),
          presets: activePresets,
          strategy_filter: strategyFilter
        })
      });
      const data = await res.json();
      if (res.ok) setResults(data);
      else alert(data.error || 'Evaluation failed');
    } catch (err) {
      alert('Failed to execute evaluation: ' + err.message);
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: 'var(--bg)' }}>
      {/* Header matching Screenshot 2 */}
      <header className="topbar">
        <div>
          <div style={{ fontSize: '1rem', fontWeight: 700 }}>Evaluation</div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Real hit-rate@k against your indexed documents</div>
        </div>
        <div style={{ flex: 1 }}></div>
        <a href="/" className="eval-btn">
          ← Back to chat
        </a>
      </header>

      <main style={{ maxWidth: '860px', width: '100%', margin: '0 auto', padding: '30px 20px', flex: 1 }}>
        {/* Section 1: TEST QUESTIONS */}
        <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: '24px', marginBottom: '24px' }}>
          <h2 style={{ fontSize: '0.82rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-primary)', marginBottom: '16px' }}>
            1. TEST QUESTIONS
          </h2>

          {/* Import File Box matching Screenshot 2 */}
          <div style={{ background: 'var(--bg-raised)', border: '1px dashed var(--border)', borderRadius: 'var(--radius-md)', padding: '14px', marginBottom: '20px' }}>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: '8px' }}>
              Import from a PDF or text file (optional)
            </div>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
              <input type="file" style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }} />
              <button className="btn-secondary" style={{ padding: '6px 16px', fontSize: '0.78rem' }}>
                Import
              </button>
            </div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '8px' }}>
              Format: one line "Q: your question", next line "A: expected section/filename", blank line between pairs.
            </div>
          </div>

          {/* Question Rows */}
          {questions.map((q, idx) => (
            <div key={idx} style={{ display: 'flex', gap: '10px', marginBottom: '10px' }}>
              <input
                type="text"
                placeholder="Question"
                value={q.question}
                onChange={(e) => updateQuestion(idx, 'question', e.target.value)}
                style={{ flex: 2, background: 'var(--bg-raised)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: '8px 12px', fontSize: '0.82rem', color: '#fff' }}
              />
              <input
                type="text"
                placeholder="Expected section/filename substring"
                value={q.expected}
                onChange={(e) => updateQuestion(idx, 'expected', e.target.value)}
                style={{ flex: 1.5, background: 'var(--bg-raised)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: '8px 12px', fontSize: '0.82rem', color: '#fff' }}
              />
              <button
                onClick={() => removeQuestion(idx)}
                style={{ background: 'none', border: '1px solid var(--border)', color: 'var(--text-muted)', borderRadius: 'var(--radius-md)', width: '36px', cursor: 'pointer' }}
              >
                ✕
              </button>
            </div>
          ))}

          <button
            onClick={addQuestion}
            className="btn-secondary"
            style={{ marginTop: '10px', padding: '6px 14px', fontSize: '0.78rem' }}
          >
            + Add question
          </button>
        </div>

        {/* Section 2: SETTINGS */}
        <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: '24px' }}>
          <h2 style={{ fontSize: '0.82rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-primary)', marginBottom: '16px' }}>
            2. SETTINGS
          </h2>

          <div style={{ display: 'flex', gap: '20px', marginBottom: '20px' }}>
            <div style={{ flex: 1 }}>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                Top-k
              </label>
              <input
                type="number"
                value={topK}
                onChange={(e) => setTopK(e.target.value)}
                style={{ width: '100%', background: 'var(--bg-raised)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: '8px 12px', fontSize: '0.85rem', color: '#fff' }}
              />
            </div>
            <div style={{ flex: 2 }}>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                Chunk strategy filter (optional)
              </label>
              <input
                type="text"
                placeholder="e.g. structured — leave blank for all"
                value={strategyFilter}
                onChange={(e) => setStrategyFilter(e.target.value)}
                style={{ width: '100%', background: 'var(--bg-raised)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: '8px 12px', fontSize: '0.85rem', color: '#fff' }}
              />
            </div>
          </div>

          <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '10px' }}>
            Ablation stages to compare
          </label>
          
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px', marginBottom: '24px' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', cursor: 'pointer' }}>
              <input type="checkbox" checked={presets['tfidf']} onChange={() => togglePreset('tfidf')} />
              <span>TF-IDF baseline</span>
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', cursor: 'pointer' }}>
              <input type="checkbox" checked={presets['bm25-qdrant-blend']} onChange={() => togglePreset('bm25-qdrant-blend')} />
              <span>BM25+Qdrant (weighted blend)</span>
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', cursor: 'pointer' }}>
              <input type="checkbox" checked={presets['bm25-qdrant-rrf']} onChange={() => togglePreset('bm25-qdrant-rrf')} />
              <span>BM25+Qdrant+RRF</span>
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', cursor: 'pointer' }}>
              <input type="checkbox" checked={presets['rrf-rerank']} onChange={() => togglePreset('rrf-rerank')} />
              <span>+ Reranking</span>
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', cursor: 'pointer' }}>
              <input type="checkbox" checked={presets['rrf-rerank-rewrite']} onChange={() => togglePreset('rrf-rerank-rewrite')} />
              <span>+ Query rewriting</span>
            </label>
          </div>

          <button
            onClick={runEval}
            disabled={isRunning}
            className="btn-primary"
            style={{ width: 'auto', padding: '10px 24px' }}
          >
            {isRunning ? 'Running evaluation...' : 'Run evaluation'}
          </button>
        </div>
      </main>
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<EvalApp />);
