const { useState, useEffect, useRef, useCallback } = React;

/* ── Temperature Helper Functions ──────────────────────────── */
function getTempClass(t) {
  if (t === 0) return 'zero';
  if (t <= 0.3) return 'low';
  if (t <= 0.7) return 'mid';
  return 'high';
}

function getTempLabel(t) {
  if (t === 0) return 'Deterministic';
  if (t <= 0.3) return 'Grounded';
  if (t <= 0.7) return 'Balanced';
  return 'Hallucination Risk';
}

/* ── Unique ID Generator Helper ────────────────────────────── */
function generateId(prefix = 'id') {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

/* ── Markdown Parser & Sanitizer Helper (P1 Security Fix) ─── */
function renderMarkdown(content) {
  if (typeof window !== 'undefined' && window.marked && typeof window.marked.parse === 'function') {
    const rawHtml = window.marked.parse(content || '');
    if (typeof window.DOMPurify !== 'undefined' && typeof window.DOMPurify.sanitize === 'function') {
      return { __html: window.DOMPurify.sanitize(rawHtml) };
    }
    // Fallback: If DOMPurify is not yet loaded, return plain text escaping
    const textNode = document.createTextNode(content || '');
    const div = document.createElement('div');
    div.appendChild(textNode);
    return { __html: div.innerHTML };
  }
  return null;
}

/* ── Phase 1: Centralized API Response Handler (P1 MUST FIX) ── */
async function handleResponse(res) {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(
      data.error || data.message || `Request failed with status ${res.status}`
    );
  }
  return data;
}

/* ── API Service Helpers ───────────────────────────────────── */
const api = {
  async getStatus() {
    const res = await fetch('/status');
    return handleResponse(res);
  },
  async uploadFiles(formData) {
    const res = await fetch('/upload', { method: 'POST', body: formData });
    return handleResponse(res);
  },
  async askQuestion(query, chunk_mode, top_k = 8, temperature = 0.0, signal) {
    const res = await fetch('/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, chunk_mode, top_k, temperature }),
      signal
    });
    return handleResponse(res);
  },
  async loadUrl(url, chunk_mode) {
    const res = await fetch('/load-url', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, chunk_mode })
    });
    return handleResponse(res);
  },
  async removeDoc(doc_id) {
    const res = await fetch('/remove', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ doc_id })
    });
    return handleResponse(res);
  },
  async clearSession() {
    const res = await fetch('/clear', { method: 'POST' });
    return handleResponse(res);
  }
};

/* ── Toast Notifications System ────────────────────────────── */
function ToastContainer({ toasts, onDismiss }) {
  if (!toasts || toasts.length === 0) return null;
  return (
    <div className="toast-container" role="region" aria-label="Notifications" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={`toast-item toast-${t.type || 'info'}`}>
          <div className="toast-content">
            <span className="toast-icon">
              {t.type === 'error' ? '⚠️' : t.type === 'success' ? '✅' : 'ℹ️'}
            </span>
            <span className="toast-message">{t.message}</span>
          </div>
          <button
            type="button"
            className="toast-close"
            onClick={() => onDismiss(t.id)}
            aria-label="Dismiss notification"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}

/* ── Source Card Component ─────────────────────────────────────
   Renders one grounded source: numbered badge, filename, page/section
   badges, score, an Open link that deep-links to the exact page with the
   matching text highlighted, and a collapsible excerpt of the actual
   retrieved chunk text. */
function SourceItem({ src, index }) {
  const [expanded, setExpanded] = useState(false);
  const scorePct = Math.max(0, Math.min(100, Math.round((src.score || 0) * 100)));
  const scoreClass = scorePct >= 80 ? 'score-high' : scorePct >= 60 ? 'score-mid' : 'score-low';

  const openHref = (() => {
    const params = new URLSearchParams();
    if (src.page) params.set('page', src.page);
    const snippet = (src.text || '').trim().slice(0, 100);
    if (snippet) params.set('hl', snippet);
    const qs = params.toString();
    const safeDocId = encodeURIComponent(String(src.doc_id));
    return `/file/${safeDocId}${qs ? `?${qs}` : ''}`;
  })();

  return (
    <div className="source-item">
      <div className="source-item-row">
        <span className="source-badge">[{index + 1}]</span>
        <span className="source-filename">📄 {src.filename}</span>
        {src.page != null && <span className="source-tag">p. {src.page}</span>}
        {src.section && <span className="source-tag">{src.section}</span>}
        <span className={`source-score ${scoreClass}`}>Score: {scorePct}%</span>
        <span className="source-item-spacer" />
        {src.openable && (
          <a
            href={openHref}
            target="_blank"
            rel="noopener noreferrer"
            className="doc-open"
            title="Open document in viewer"
          >
            Open ↗
          </a>
        )}
        {src.text && (
          <button
            type="button"
            className="view-content-toggle"
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
            aria-label={expanded ? `Hide excerpt for source ${index + 1}` : `View excerpt for source ${index + 1}`}
          >
            {expanded ? '▲ Hide' : '▼ View Content'}
          </button>
        )}
      </div>
      {expanded && src.text && (
        <div className="source-excerpt-wrap">
          <div className="source-excerpt-label">
            📄 DOCUMENT EXCERPT [{index + 1}]
            {src.method && <span className="source-excerpt-strategy"> · STRATEGY: {src.method.toUpperCase()}</span>}
          </div>
          <div className="source-excerpt">{src.text}</div>
        </div>
      )}
    </div>
  );
}

/* ── Topbar Component ──────────────────────────────────────── */
function Topbar({ backendMode, backendStatus, docsCount, retrievalMode, topK, temperature, sidebarOpen, onToggleSidebar }) {
  const statusLabel =
    backendStatus === 'healthy' ? 'Connected' : backendStatus === 'checking' ? 'Connecting...' : 'Disconnected';

  return (
    <header className="topbar">
      <div className="topbar-logo">
        <button
          type="button"
          className={`logo-toggle-btn ${sidebarOpen ? 'active' : 'collapsed'}`}
          onClick={onToggleSidebar}
          title={sidebarOpen ? "Hide Sidebar (Collapse)" : "Show Sidebar (Open)"}
          aria-label={sidebarOpen ? "Collapse sidebar navigation" : "Expand sidebar navigation"}
        >
          <span className="hamburger-line"></span>
          <span className="hamburger-line"></span>
          <span className="hamburger-line"></span>
        </button>
        <span className="logo-name">Ask My Docs</span>
        <span className="logo-version">v1 · Python</span>
      </div>

      <div className="topbar-spacer"></div>

      <a href="/eval" className="eval-btn">
        Evaluate ↗
      </a>

      <div className="topbar-stat">
        <span
          className={`status-dot status-${backendStatus}`}
          title={`Backend status: ${statusLabel}`}
          aria-label={`Backend status: ${statusLabel}`}
        ></span>
        <span>Docs: {docsCount}</span>
        <span className="topbar-mode">K={topK} · T={temperature.toFixed(2)}</span>
        {retrievalMode && (
          <span className="topbar-mode topbar-mode-hybrid">
            mode: {retrievalMode}
          </span>
        )}
        <span className="topbar-mode topbar-mode-backend">
          {backendMode || 'qdrant'}
        </span>
      </div>
    </header>
  );
}

/* ── Sidebar Component ─────────────────────────────────────── */
function Sidebar({
  strategy,
  setStrategy,
  setStrategySelected,
  topK,
  setTopK,
  temperature,
  setTemperature,
  files,
  onUpload,
  onLoadUrl,
  onRemoveDoc,
  onClear,
  isUploading,
  isThinking,
  selectedFiles,
  onAddSelectedFiles,
  onRemoveSelectedFile,
  onClearSelectedFiles
}) {
  const [dragActive, setDragActive] = useState(false);
  const [urlInput, setUrlInput] = useState('');
  const [isLoadingUrl, setIsLoadingUrl] = useState(false);
  const [showCompare, setShowCompare] = useState(false);
  const [topKInput, setTopKInput] = useState(String(topK));
  const fileInputRef = useRef(null);

  useEffect(() => {
    setTopKInput(String(topK));
  }, [topK]);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (isThinking || isUploading) return;
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true);
    else if (e.type === 'dragleave') setDragActive(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (isThinking || isUploading) return;
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      onAddSelectedFiles(Array.from(e.dataTransfer.files));
    }
  };

  const handleFileInputChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      onAddSelectedFiles(Array.from(e.target.files));
      e.target.value = '';
    }
  };

  const handleUrlSubmit = async (e) => {
    e.preventDefault();
    const targetUrl = urlInput.trim();
    if (!targetUrl || isThinking || isLoadingUrl) return;
    setIsLoadingUrl(true);
    try {
      await onLoadUrl(targetUrl);
      setUrlInput('');
    } finally {
      setIsLoadingUrl(false);
    }
  };

  const handleTopKInputChange = (e) => {
    const rawVal = e.target.value;
    setTopKInput(rawVal);
    if (/^\d+$/.test(rawVal)) {
      const parsed = parseInt(rawVal, 10);
      if (parsed >= 1 && parsed <= 20) {
        setTopK(parsed);
      }
    }
  };

  const handleTopKInputBlur = () => {
    const trimmed = topKInput.trim();
    if (!/^\d+$/.test(trimmed)) {
      setTopK(8);
      setTopKInput('8');
      return;
    }
    const parsed = parseInt(trimmed, 10);
    if (parsed < 1) {
      setTopK(1);
      setTopKInput('1');
    } else if (parsed > 20) {
      setTopK(20);
      setTopKInput('20');
    } else {
      setTopK(parsed);
      setTopKInput(String(parsed));
    }
  };

  const isReadyToUpload = selectedFiles.length > 0;
  const isBusy = isUploading || isThinking;

  return (
    <aside className="sidebar">
      {/* 1. UPLOAD DOCUMENTS */}
      <div className="sidebar-section">
        <div className="sidebar-label">UPLOAD DOCUMENTS</div>
        
        <label
          htmlFor="sidebar-file-input"
          className={`dropzone ${dragActive ? 'active' : ''} ${isReadyToUpload ? 'file-ready' : ''} ${isBusy ? 'disabled' : ''}`}
          tabIndex={isBusy ? -1 : 0}
          aria-label="Upload documents dropzone. Click or press Enter to choose files."
          onDragEnter={handleDrag}
          onDragOver={handleDrag}
          onDragLeave={handleDrag}
          onDrop={handleDrop}
          onKeyDown={(e) => {
            if (!isBusy && (e.key === 'Enter' || e.key === ' ')) {
              e.preventDefault();
              fileInputRef.current?.click();
            }
          }}
        >
          <input
            id="sidebar-file-input"
            ref={fileInputRef}
            type="file"
            multiple
            disabled={isBusy}
            accept=".pdf,.txt,.md,.markdown,.docx,.doc,.csv,.tsv,.json,.yaml,.yml,.xml,.py,.js,.ts,.jsx,.tsx,.html,.css,.c,.cpp,.java,.go,.rs,.php,.sql,.sh,.png,.jpg,.jpeg,.webp,.bmp"
            className="file-input-hidden"
            onChange={handleFileInputChange}
          />
          <div className="dropzone-icon">📁</div>
          <div className="dropzone-title">
            {isReadyToUpload
              ? `${selectedFiles.length} file(s) selected`
              : 'Drop files here'}
          </div>
          <div className="dropzone-sub">
            {isReadyToUpload ? 'Click or drop more files to add' : 'PDF, Word, TXT, CSV, Code, or Images'}
          </div>
        </label>

        {/* Selected Queued Staged Files List with Object URL Clean Lifecycle */}
        {isReadyToUpload && (
          <div className="staged-files-list">
            <div className="staged-files-header">
              Files queued to index:
            </div>
            {selectedFiles.map((f) => (
              <div key={f.id} className="staged-file-item">
                <span className="doc-name" title={f.name}>📄 {f.name}</span>
                <div className="staged-actions">
                  {f.previewUrl && (
                    <a
                      href={f.previewUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="doc-open"
                      title="Preview local staged file"
                      onClick={(e) => e.stopPropagation()}
                    >
                      Open ↗
                    </a>
                  )}
                  <button
                    type="button"
                    className="doc-remove"
                    disabled={isBusy}
                    onClick={(e) => {
                      e.stopPropagation();
                      onRemoveSelectedFile(f.id);
                    }}
                    title="Remove file from selection"
                    aria-label={`Remove ${f.name} from selection`}
                  >
                    ✕
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 2. CHUNKING STRATEGY */}
      <div className="sidebar-section">
        <div className="sidebar-label">CHUNKING STRATEGY</div>
        
        <select
          value={strategy}
          onChange={(e) => {
            setStrategy(e.target.value);
            if (setStrategySelected) setStrategySelected(true);
          }}
          className="strategy-select"
          disabled={isBusy}
          aria-label="Select chunking strategy"
        >
          <option value="structured">Structured</option>
          <option value="128">128 Words</option>
          <option value="256">256 Words</option>
          <option value="512">512 Words</option>
        </select>

        <button
          type="button"
          className="compare-link"
          aria-expanded={showCompare}
          onClick={() => setShowCompare((v) => !v)}
        >
          {showCompare ? '▴ Hide chunk details' : '▾ Compare chunk sizes'}
        </button>

        {showCompare && (
          <div className="compare-details-box">
            <div>• <strong>Structured</strong>: Semantic headings & paragraphs</div>
            <div>• <strong>128 words</strong>: Fine-grained window</div>
            <div>• <strong>256 words</strong>: Medium balanced</div>
            <div>• <strong>512 words</strong>: Broad window</div>
          </div>
        )}

        <div className="sidebar-btn-row">
          <button
            type="button"
            onClick={() => isReadyToUpload && !isBusy && onUpload(selectedFiles)}
            disabled={!isReadyToUpload || isBusy}
            className={`btn-primary btn-upload-primary ${isReadyToUpload && !isBusy ? 'pulse' : ''}`}
          >
            {isUploading ? 'Uploading...' : '↑ Upload & Index'}
          </button>
          <button
            type="button"
            onClick={onClearSelectedFiles}
            disabled={!isReadyToUpload || isBusy}
            className="btn-secondary btn-cancel-staged"
          >
            Cancel
          </button>
        </div>
      </div>

      {/* 3. RAG CONTROLS & GENERATION PARAMETERS */}
      <div className="sidebar-section">
        <div className="sidebar-label">RAG PARAMETERS & CONTROLS</div>

        {/* Top-K Stepper */}
        <div className="param-control-group">
          <div className="param-header">
            <span className="param-title">Retrieval Top-K</span>
            <span className="param-badge">K = {topK}</span>
          </div>
          <div className="stepper-wrap">
            <button
              type="button"
              className="stepper-btn"
              disabled={topK <= 1 || isBusy}
              onClick={() => setTopK((k) => Math.max(1, k - 1))}
              title="Decrease Top-K"
              aria-label="Decrease retrieval Top-K"
            >
              −
            </button>
            <input
              type="number"
              min="1"
              max="20"
              value={topKInput}
              disabled={isBusy}
              onChange={handleTopKInputChange}
              onBlur={handleTopKInputBlur}
              className="stepper-input"
              aria-label="Retrieval Top-K value"
            />
            <button
              type="button"
              className="stepper-btn"
              disabled={topK >= 20 || isBusy}
              onClick={() => setTopK((k) => Math.min(20, k + 1))}
              title="Increase Top-K"
              aria-label="Increase retrieval Top-K"
            >
              +
            </button>
          </div>
          <div className="quick-pills">
            {[3, 5, 8, 12, 16].map((p) => (
              <button
                key={p}
                type="button"
                disabled={isBusy}
                className={`quick-pill ${topK === p ? 'active' : ''}`}
                onClick={() => setTopK(p)}
                aria-label={`Set Top-K to ${p}`}
              >
                {p}
              </button>
            ))}
          </div>
          <div className="param-hint">Number of context candidates retrieved (Default: 8)</div>
        </div>

        {/* Temperature Slider */}
        <div className="param-control-group param-group-spaced">
          <div className="param-header">
            <span className="param-title">Generation Temperature</span>
            <span className={`temp-badge temp-${getTempClass(temperature)}`}>
              {temperature.toFixed(2)} · {getTempLabel(temperature)}
            </span>
          </div>
          <div className="slider-wrap">
            <input
              type="range"
              min="0.0"
              max="1.0"
              step="0.05"
              value={temperature}
              disabled={isBusy}
              onChange={(e) => setTemperature(parseFloat(e.target.value))}
              className="temp-slider"
              aria-label="Generation temperature slider"
            />
            <div className="slider-ticks">
              <span>0.0 (Strict)</span>
              <span>0.5 (Balanced)</span>
              <span>1.0 (Creative/Test)</span>
            </div>
          </div>
          <div className="param-hint">
            Set 0.0 for strict factuality, or &gt;0.7 to evaluate hallucination risk.
          </div>
        </div>
      </div>

      {/* 4. OR LOAD A WEB PAGE */}
      <div className="sidebar-section">
        <div className="sidebar-label">OR LOAD A WEB PAGE</div>
        
        <form onSubmit={handleUrlSubmit}>
          <input
            type="url"
            placeholder="https://example.com/article"
            value={urlInput}
            disabled={isBusy || isLoadingUrl}
            onChange={(e) => setUrlInput(e.target.value)}
            className="url-input-field"
            aria-label="Web article URL to fetch and index"
          />
          <button
            type="submit"
            disabled={isBusy || isLoadingUrl || !urlInput.trim()}
            className="btn-green"
          >
            {isLoadingUrl ? 'Loading...' : '🌐 Fetch & Index'}
          </button>
        </form>
      </div>

      {/* 5. DOCUMENTS */}
      <div className="sidebar-section sidebar-section-grow">
        <div className="sidebar-label">DOCUMENTS</div>

        {files.length === 0 ? (
          <div className="doc-empty-state">
            No documents loaded
          </div>
        ) : (
          <div className="doc-list">
            {files.map((f) => {
              const displayName = f.filename || f.name || 'Untitled Document';
              return (
                <div key={f.doc_id} className="doc-item">
                  <span className="doc-name" title={displayName}>
                    📄 {displayName}
                  </span>
                  <div className="doc-item-actions">
                    <a
                      href={`/file/${encodeURIComponent(String(f.doc_id))}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="doc-open"
                      title="Open document in new viewer tab"
                    >
                      Open ↗
                    </a>
                    <button
                      type="button"
                      className="doc-remove"
                      disabled={isBusy}
                      onClick={() => onRemoveDoc(f.doc_id)}
                      title={`Remove document ${displayName}`}
                      aria-label={`Remove document ${displayName}`}
                    >
                      ✕
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {files.length > 0 && (
          <button
            type="button"
            onClick={onClear}
            disabled={isBusy}
            className="btn-secondary btn-clear-danger"
          >
            🗑 Clear all documents
          </button>
        )}
      </div>
    </aside>
  );
}

/* ── Chat Container Component ────────────────────────────────── */
function ChatArea({ messages, onSend, isThinking, filesCount, selectedFilesCount, strategy, strategySelected }) {
  const [input, setInput] = useState('');
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isThinking]);

  const handleSubmit = (e) => {
    e.preventDefault();
    const query = input.trim();
    if (!query || isThinking) return;
    onSend(query);
    setInput('');
  };

  /* ── Sequential Onboarding State Machine (P2 Enhanced) ─────── */
  const hasIndexedDocs = filesCount > 0;
  const hasStagedFiles = selectedFilesCount > 0;

  // Step 1: Upload / select document
  const isStep1Done = hasStagedFiles || hasIndexedDocs;
  const isStep1Active = !hasStagedFiles && !hasIndexedDocs;

  // Step 2: Choose chunking strategy
  const isStep2Done = strategySelected || hasIndexedDocs;
  const isStep2Active = hasStagedFiles && !strategySelected && !hasIndexedDocs;

  // Step 3: Upload & Index
  const isStep3Done = hasIndexedDocs;
  const isStep3Active = hasStagedFiles && (strategySelected || strategy === 'structured') && !hasIndexedDocs;

  // Step 4: Ask a question
  const isStep4Active = hasIndexedDocs;

  return (
    <main className="chat-container">
      <div className="messages-area">
        {messages.length === 0 ? (
          <div className="onboarding-container">
            <div className="onboarding-icon">💬</div>
            <h2 className="onboarding-title">Ask questions about your documents</h2>
            <p className="onboarding-sub">
              Answers are based only on your indexed documents and include source references.
            </p>

            <div className="onboarding-steps">
              <div className={`onboarding-step ${isStep1Done ? 'completed' : isStep1Active ? 'active' : ''}`}>
                {isStep1Done ? (
                  <div className="onboarding-step-check">✓</div>
                ) : (
                  <div className="onboarding-step-radio"></div>
                )}
                <span>1. Upload your document</span>
              </div>

              <div className={`onboarding-step ${isStep2Done ? 'completed' : isStep2Active ? 'active' : ''}`}>
                {isStep2Done ? (
                  <div className="onboarding-step-check">✓</div>
                ) : (
                  <div className="onboarding-step-radio"></div>
                )}
                <span>2. Configure chunking strategy</span>
              </div>

              <div className={`onboarding-step ${isStep3Done ? 'completed' : isStep3Active ? 'active' : ''}`}>
                {isStep3Done ? (
                  <div className="onboarding-step-check">✓</div>
                ) : (
                  <div className="onboarding-step-radio"></div>
                )}
                <span>3. Upload & Index</span>
              </div>

              <div className={`onboarding-step ${isStep4Active ? 'active' : ''}`}>
                <div className="onboarding-step-radio"></div>
                <span>4. Ask a question</span>
              </div>
            </div>
          </div>
        ) : (
          messages.map((m) => (
            <div key={m.id} className={`message-row ${m.role}`}>
              <div className={`message-bubble ${m.role === 'ai' ? 'message-ai-content' : ''}`}>
                {m.role === 'ai' && typeof window !== 'undefined' && window.marked ? (
                  <div dangerouslySetInnerHTML={renderMarkdown(m.text)} />
                ) : (
                  <div>{m.text}</div>
                )}
                {m.sources && m.sources.length > 0 && (
                  <div className="sources-card">
                    <div className="sources-header">📄 GROUNDED SOURCES ({m.sources.length})</div>
                    {m.sources.map((src, i) => (
                      <SourceItem
                        key={`${src.doc_id || 'doc'}-${src.page || 'p'}-${i}`}
                        src={src}
                        index={i}
                      />
                    ))}
                  </div>
                )}
                {m.role === 'ai' && (
                  <div className="message-meta-bar">
                    <span className="meta-pill">🎯 Top-K: {m.topK != null ? m.topK : 8}</span>
                    <span className="meta-pill">🌡️ Temp: {m.temperature != null ? Number(m.temperature).toFixed(2) : '0.00'}</span>
                    {m.sources && <span className="meta-pill">📄 {m.sources.length} sources</span>}
                  </div>
                )}
              </div>
            </div>
          ))
        )}

        {isThinking && (
          <div className="message-row ai">
            <div className="message-bubble message-thinking">
              Generating grounded answer...
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="input-bar-container">
        <form onSubmit={handleSubmit} className="input-bar-pill">
          <input
            type="text"
            className="query-input-field"
            placeholder="Ask a question..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isThinking}
            aria-label="Ask a question about your documents"
          />
          <button
            type="submit"
            className="send-pill-btn"
            disabled={!input.trim() || isThinking}
            aria-label="Send question"
          >
            ➤
          </button>
        </form>
      </div>
    </main>
  );
}

/* ── Root App Component ──────────────────────────────────────── */
function App() {
  const [sidebarOpen, setSidebarOpen] = useState(() => (typeof window !== 'undefined' ? window.innerWidth > 700 : true));
  const [backendMode, setBackendMode] = useState('');
  const [backendStatus, setBackendStatus] = useState('checking'); // 'checking' | 'healthy' | 'error'
  const [retrievalMode, setRetrievalMode] = useState('hybrid');
  const [files, setFiles] = useState([]);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [strategy, setStrategy] = useState('structured');
  const [strategySelected, setStrategySelected] = useState(false);
  const [topK, setTopK] = useState(8);
  const [temperature, setTemperature] = useState(0.0);
  const [messages, setMessages] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [toasts, setToasts] = useState([]);

  const activeAbortControllerRef = useRef(null);
  const toastTimersRef = useRef(new Map());
  const selectedFilesRef = useRef(selectedFiles);

  useEffect(() => {
    selectedFilesRef.current = selectedFiles;
  }, [selectedFiles]);

  const dismissToast = useCallback((id) => {
    if (toastTimersRef.current.has(id)) {
      clearTimeout(toastTimersRef.current.get(id));
      toastTimersRef.current.delete(id);
    }
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback((message, type = 'info', duration = 5000) => {
    const id = generateId('toast');
    setToasts((prev) => [...prev, { id, message, type }]);
    if (duration > 0) {
      const timer = setTimeout(() => {
        dismissToast(id);
      }, duration);
      toastTimersRef.current.set(id, timer);
    }
  }, [dismissToast]);

  // Clean up all toast timers on component unmount
  useEffect(() => {
    return () => {
      toastTimersRef.current.forEach((timer) => clearTimeout(timer));
      toastTimersRef.current.clear();
    };
  }, []);

  // Display toast after browser hard refresh (Ctrl+Shift+R / Cmd+Shift+R / Ctrl+F5)
  useEffect(() => {
    const HARD_REFRESH_TOAST_KEY = 'ask-my-docs-hard-refresh';
    try {
      if (sessionStorage.getItem(HARD_REFRESH_TOAST_KEY) === '1') {
        sessionStorage.removeItem(HARD_REFRESH_TOAST_KEY);
        const timer = setTimeout(() => {
          showToast('↻ Hard refresh completed. Latest resources loaded.', 'success', 3500);
        }, 300);
        return () => clearTimeout(timer);
      }
    } catch (e) {
      // Gracefully handle restricted storage environments
    }
  }, [showToast]);

  // Global key listener to detect hard refresh combinations before page unload
  useEffect(() => {
    const HARD_REFRESH_TOAST_KEY = 'ask-my-docs-hard-refresh';
    const handleKeyDown = (event) => {
      const isHardRefresh =
        (event.shiftKey && (event.ctrlKey || event.metaKey) && event.key && event.key.toLowerCase() === 'r') ||
        ((event.ctrlKey || event.shiftKey) && (event.key === 'F5' || event.code === 'F5'));

      if (isHardRefresh) {
        try {
          sessionStorage.setItem(HARD_REFRESH_TOAST_KEY, '1');
        } catch (e) {
          // Gracefully handle storage write errors
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Staged files lifecycle management with preview URLs
  const handleAddSelectedFiles = useCallback((rawFiles) => {
    const newItems = rawFiles.map((file) => ({
      id: generateId('staged'),
      file,
      name: file.name,
      previewUrl: typeof URL !== 'undefined' && typeof URL.createObjectURL === 'function' ? URL.createObjectURL(file) : null
    }));
    setSelectedFiles((prev) => [...prev, ...newItems]);
  }, []);

  const handleRemoveSelectedFile = useCallback((idToRemove) => {
    setSelectedFiles((prev) => {
      const target = prev.find((item) => item.id === idToRemove);
      if (target && target.previewUrl && typeof URL !== 'undefined' && typeof URL.revokeObjectURL === 'function') {
        URL.revokeObjectURL(target.previewUrl);
      }
      return prev.filter((item) => item.id !== idToRemove);
    });
  }, []);

  const handleClearSelectedFiles = useCallback(() => {
    setSelectedFiles((prev) => {
      prev.forEach((item) => {
        if (item.previewUrl && typeof URL !== 'undefined' && typeof URL.revokeObjectURL === 'function') {
          URL.revokeObjectURL(item.previewUrl);
        }
      });
      return [];
    });
  }, []);

  // Cleanup all staged URLs strictly on component unmount
  useEffect(() => {
    return () => {
      selectedFilesRef.current.forEach((item) => {
        if (item.previewUrl && typeof URL !== 'undefined' && typeof URL.revokeObjectURL === 'function') {
          URL.revokeObjectURL(item.previewUrl);
        }
      });
    };
  }, []);

  const fetchStatus = useCallback(async () => {
    try {
      const status = await api.getStatus();
      setFiles(status.documents || []);
      if (status.vector_backend) setBackendMode(status.vector_backend);
      if (status.mode) setRetrievalMode(status.mode);
      setBackendStatus('healthy');
    } catch (err) {
      console.error("Failed to fetch status:", err);
      setBackendStatus('error');
      showToast('Could not connect to backend server: ' + err.message, 'error', 6000);
    }
  }, [showToast]);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  // Synchronize Sidebar with Viewport Resize and Media Query Listener
  useEffect(() => {
    const mql = window.matchMedia('(max-width: 700px)');
    const handleMediaChange = (e) => {
      if (e.matches) {
        setSidebarOpen(false);
      } else {
        setSidebarOpen(true);
      }
    };

    if (mql.addEventListener) {
      mql.addEventListener('change', handleMediaChange);
    } else {
      mql.addListener(handleMediaChange);
    }

    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && sidebarOpen && window.innerWidth <= 700) {
        setSidebarOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);

    return () => {
      if (mql.removeEventListener) {
        mql.removeEventListener('change', handleMediaChange);
      } else {
        mql.removeListener(handleMediaChange);
      }
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [sidebarOpen]);

  const handleUpload = async (stagedList) => {
    if (!stagedList || stagedList.length === 0 || isThinking || isUploading) return;
    setIsUploading(true);
    const formData = new FormData();
    stagedList.forEach((item) => formData.append('files', item.file));
    formData.append('chunk_mode', strategy);

    try {
      const res = await api.uploadFiles(formData);
      handleClearSelectedFiles();
      await fetchStatus();
      const failed = (res.documents || []).filter((d) => d.error);
      const degraded = (res.documents || []).filter((d) => d.warning);
      if (failed.length > 0) {
        showToast(
          `${failed.length} file(s) failed: ${failed.map((d) => d.filename + ' (' + d.error + ')').join(', ')}`,
          'error',
          7000
        );
      } else if (degraded.length > 0) {
        showToast(
          `${degraded.length} file(s) indexed with warnings: ${degraded.map((d) => d.filename).join(', ')}`,
          'info',
          6000
        );
      } else {
        showToast('Documents uploaded and indexed successfully!', 'success', 4000);
      }
    } catch (err) {
      showToast('Upload failed: ' + err.message, 'error', 6000);
    } finally {
      setIsUploading(false);
    }
  };

  const handleLoadUrl = async (url) => {
    if (isThinking || isUploading) return;
    try {
      await api.loadUrl(url, strategy);
      await fetchStatus();
      showToast('Web page fetched and indexed successfully!', 'success', 4000);
    } catch (err) {
      showToast('Failed to load URL: ' + err.message, 'error', 6000);
    }
  };

  const handleRemoveDoc = async (doc_id) => {
    if (isThinking || isUploading) return;
    try {
      await api.removeDoc(doc_id);
      await fetchStatus();
      showToast('Document removed from index.', 'info', 3000);
    } catch (err) {
      showToast('Failed to remove document: ' + err.message, 'error', 6000);
    }
  };

  const handleClear = async () => {
    if (isThinking || isUploading) return;
    try {
      await api.clearSession();
      setMessages([]);
      await fetchStatus();
      showToast('All documents and chat history cleared.', 'info', 3000);
    } catch (err) {
      showToast('Failed to clear documents: ' + err.message, 'error', 6000);
    }
  };

  const handleSend = async (query) => {
    if (isThinking || isUploading) return;
    const userMsg = { id: generateId('user-msg'), role: 'user', text: query };
    setMessages((prev) => [...prev, userMsg]);
    setIsThinking(true);

    const controller = new AbortController();
    activeAbortControllerRef.current = controller;

    try {
      const res = await api.askQuestion(query, strategy, topK, temperature, controller.signal);
      const aiMsg = {
        id: generateId('ai-msg'),
        role: 'ai',
        text: res.answer || "I don't know.",
        sources: res.sources || [],
        query,
        topK: res.top_k != null ? res.top_k : topK,
        temperature: res.temperature != null ? res.temperature : temperature,
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch (err) {
      if (err.name === 'AbortError') {
        return;
      }
      setMessages((prev) => [
        ...prev,
        {
          id: generateId('err-msg'),
          role: 'ai',
          text: 'Error executing query: ' + err.message,
          topK,
          temperature
        }
      ]);
      showToast('Query error: ' + err.message, 'error', 6000);
    } finally {
      setIsThinking(false);
      activeAbortControllerRef.current = null;
    }
  };

  return (
    <div className={`layout ${sidebarOpen ? '' : 'sidebar-collapsed'}`}>
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
      <Topbar
        backendMode={backendMode}
        backendStatus={backendStatus}
        docsCount={files.length}
        retrievalMode={retrievalMode}
        topK={topK}
        temperature={temperature}
        sidebarOpen={sidebarOpen}
        onToggleSidebar={() => setSidebarOpen((v) => !v)}
      />
      <div
        className="sidebar-backdrop"
        onClick={() => setSidebarOpen(false)}
        aria-hidden="true"
      />
      <Sidebar
        strategy={strategy}
        setStrategy={setStrategy}
        setStrategySelected={setStrategySelected}
        topK={topK}
        setTopK={setTopK}
        temperature={temperature}
        setTemperature={setTemperature}
        files={files}
        onUpload={handleUpload}
        onLoadUrl={handleLoadUrl}
        onRemoveDoc={handleRemoveDoc}
        onClear={handleClear}
        isUploading={isUploading}
        isThinking={isThinking}
        selectedFiles={selectedFiles}
        onAddSelectedFiles={handleAddSelectedFiles}
        onRemoveSelectedFile={handleRemoveSelectedFile}
        onClearSelectedFiles={handleClearSelectedFiles}
      />
      <ChatArea
        messages={messages}
        onSend={handleSend}
        isThinking={isThinking}
        filesCount={files.length}
        selectedFilesCount={selectedFiles.length}
        strategy={strategy}
        strategySelected={strategySelected}
      />
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
