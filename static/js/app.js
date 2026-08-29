const { useState, useEffect, useRef, useCallback } = React;

/* ── API Service Helpers ───────────────────────────────────── */
const api = {
  async getStatus() {
    const res = await fetch('/status');
    return res.json();
  },
  async uploadFiles(formData) {
    const res = await fetch('/upload', { method: 'POST', body: formData });
    return res.json();
  },
  async askQuestion(query, chunk_mode) {
    const res = await fetch('/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, chunk_mode })
    });
    return res.json();
  },
  async loadUrl(url, chunk_mode) {
    const res = await fetch('/load-url', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, chunk_mode })
    });
    return res.json();
  },
  async removeDoc(doc_id) {
    const res = await fetch('/remove', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ doc_id })
    });
    return res.json();
  },
  async clearSession() {
    const res = await fetch('/clear', { method: 'POST' });
    return res.json();
  }
};

/* ── Topbar Component ──────────────────────────────────────── */
function Topbar({ backendMode, docsCount, retrievalMode }) {
  return (
    <header className="topbar">
      <div className="topbar-logo">
        <div className="logo-icon">≡</div>
        <span className="logo-name">Ask My Docs</span>
        <span className="logo-version">v1 · Python</span>
      </div>

      <div style={{ flex: 1 }}></div>

      <a href="/eval" className="eval-btn">
        Evaluate ↗
      </a>

      <div className="topbar-stat">
        <span className="status-dot"></span>
        <span>Documents: {docsCount}</span>
        <span className="topbar-mode">Retrieval: {retrievalMode || 'hybrid'}</span>
        <span className="topbar-mode" style={{ background: 'var(--purple-dim)', color: 'var(--purple)' }}>
          Backend: {backendMode || 'qdrant'}
        </span>
      </div>
    </header>
  );
}

/* ── Sidebar Component ─────────────────────────────────────── */
function Sidebar({
  strategy,
  setStrategy,
  files,
  onUpload,
  onLoadUrl,
  onRemoveDoc,
  onClear,
  isUploading,
  selectedFiles,
  setSelectedFiles
}) {
  const [dragActive, setDragActive] = useState(false);
  const [urlInput, setUrlInput] = useState('');
  const [isLoadingUrl, setIsLoadingUrl] = useState(false);
  const [showCompare, setShowCompare] = useState(false);
  const fileInputRef = useRef(null);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true);
    else if (e.type === 'dragleave') setDragActive(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setSelectedFiles((prev) => [...prev, ...Array.from(e.dataTransfer.files)]);
    }
  };

  const handleRemoveSelected = (indexToRemove) => {
    setSelectedFiles((prev) => prev.filter((_, idx) => idx !== indexToRemove));
  };

  const handleUrlSubmit = async (e) => {
    e.preventDefault();
    if (!urlInput.trim()) return;
    setIsLoadingUrl(true);
    try {
      await onLoadUrl(urlInput.trim());
      setUrlInput('');
    } finally {
      setIsLoadingUrl(false);
    }
  };

  const isReadyToUpload = selectedFiles.length > 0;

  return (
    <aside className="sidebar">
      {/* 1. UPLOAD DOCUMENTS */}
      <div className="sidebar-section">
        <div className="sidebar-label">UPLOAD DOCUMENTS</div>
        
        <div
          className={`dropzone ${dragActive ? 'active' : ''} ${isReadyToUpload ? 'file-ready' : ''}`}
          onDragEnter={handleDrag}
          onDragOver={handleDrag}
          onDragLeave={handleDrag}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.txt,.md,.markdown,.docx,.doc,.csv,.tsv,.json,.yaml,.yml,.xml,.py,.js,.ts,.jsx,.tsx,.html,.css,.c,.cpp,.java,.go,.rs,.php,.sql,.sh,.png,.jpg,.jpeg,.webp,.bmp"
            style={{ display: 'none' }}
            onChange={(e) => e.target.files?.length && setSelectedFiles((prev) => [...prev, ...Array.from(e.target.files)])}
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
        </div>

        {/* Selected Queued Staged Files List with BOTH Open ↗ and ✕ Remove Buttons */}
        {isReadyToUpload && (
          <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--amber)', fontWeight: 700 }}>
              Files queued to index:
            </div>
            {selectedFiles.map((f, idx) => (
              <div key={idx} className="staged-file-item">
                <span className="doc-name" title={f.name}>📄 {f.name}</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <a
                    href={URL.createObjectURL(f)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="doc-open"
                    title="Preview local staged file"
                    onClick={(e) => e.stopPropagation()}
                  >
                    Open ↗
                  </a>
                  <button
                    className="doc-remove"
                    onClick={(e) => { e.stopPropagation(); handleRemoveSelected(idx); }}
                    title="Remove file from selection"
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
          onChange={(e) => setStrategy(e.target.value)}
          className="strategy-select"
        >
          <option value="structured">Structured</option>
          <option value="128">128 Words</option>
          <option value="256">256 Words</option>
          <option value="512">512 Words</option>
        </select>

        <div className="compare-link" onClick={() => setShowCompare(!showCompare)}>
          {showCompare ? '▴ Compare chunk sizes' : '▾ Compare chunk sizes'}
        </div>

        {showCompare && (
          <div style={{ background: 'var(--bg-raised)', padding: '8px 10px', borderRadius: 'var(--radius-sm)', marginTop: '6px', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
            <div>• <strong>Structured</strong>: Semantic headings & paragraphs</div>
            <div>• <strong>128 words</strong>: Fine-grained window</div>
            <div>• <strong>256 words</strong>: Medium balanced</div>
            <div>• <strong>512 words</strong>: Broad window</div>
          </div>
        )}

        <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
          <button
            onClick={() => isReadyToUpload && onUpload(selectedFiles)}
            disabled={!isReadyToUpload || isUploading}
            className={`btn-primary ${isReadyToUpload ? 'pulse' : ''}`}
            style={{ flex: 2 }}
          >
            {isUploading ? 'Uploading...' : '↑ Upload & Index document'}
          </button>
          <button
            onClick={() => setSelectedFiles([])}
            disabled={!isReadyToUpload}
            className="btn-secondary"
            style={{ flex: 1 }}
          >
            Cancel
          </button>
        </div>
      </div>

      {/* 3. OR LOAD A WEB PAGE */}
      <div className="sidebar-section">
        <div className="sidebar-label">OR LOAD A WEB PAGE</div>
        
        <form onSubmit={handleUrlSubmit}>
          <input
            type="url"
            placeholder="https://example.com/article"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            className="query-input-field"
            style={{ width: '100%', background: 'var(--bg-raised)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: '10px 12px', fontSize: '0.8rem', color: '#fff' }}
          />
          <button
            type="submit"
            disabled={isLoadingUrl || !urlInput.trim()}
            className="btn-green"
          >
            {isLoadingUrl ? 'Loading...' : '🌐 Fetch & Index'}
          </button>
        </form>
      </div>

      {/* 4. DOCUMENTS (Indexed files with full filename display, Open ↗ and ✕ Remove buttons) */}
      <div className="sidebar-section" style={{ flex: 1 }}>
        <div className="sidebar-label">DOCUMENTS</div>

        {files.length === 0 ? (
          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textAlign: 'center', padding: '16px 0' }}>
            No documents loaded
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {files.map((f) => {
              const displayName = f.filename || f.name || 'Untitled Document';
              return (
                <div key={f.doc_id} className="doc-item">
                  <span className="doc-name" title={displayName}>
                    📄 {displayName}
                  </span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <a
                      href={`/file/${f.doc_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="doc-open"
                      title="Open document in new viewer tab"
                    >
                      Open ↗
                    </a>
                    <button
                      className="doc-remove"
                      onClick={() => onRemoveDoc(f.doc_id)}
                      title="Remove document from index"
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
            onClick={onClear}
            className="btn-secondary"
            style={{ width: '100%', marginTop: '16px', color: 'var(--red)', borderColor: 'var(--red-dim)' }}
          >
            🗑 Clear all documents
          </button>
        )}
      </div>
    </aside>
  );
}

/* ── Chat Container Component ────────────────────────────────── */
function ChatArea({ messages, onSend, isThinking, filesCount, selectedFilesCount }) {
  const [input, setInput] = useState('');
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isThinking]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!input.trim() || isThinking) return;
    onSend(input.trim());
    setInput('');
  };

  const isStep1Done = selectedFilesCount > 0 || filesCount > 0;
  const isStep2Done = selectedFilesCount > 0 || filesCount > 0;
  const isStep3Done = filesCount > 0;
  const isStep3Active = selectedFilesCount > 0 && filesCount === 0;
  const isStep4Active = filesCount > 0;

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
              <div className={`onboarding-step ${isStep1Done ? 'completed' : 'active'}`}>
                {isStep1Done ? (
                  <div className="onboarding-step-check">✓</div>
                ) : (
                  <div className="onboarding-step-radio"></div>
                )}
                <span>1. Upload your document</span>
              </div>

              <div className={`onboarding-step ${isStep2Done ? 'completed' : ''}`}>
                {isStep2Done ? (
                  <div className="onboarding-step-check">✓</div>
                ) : (
                  <div className="onboarding-step-radio"></div>
                )}
                <span>2. Choose a chunking strategy</span>
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
          messages.map((m, idx) => (
            <div key={idx} className={`message-row ${m.role}`}>
              <div className="message-bubble">
                <div>{m.text}</div>
                {m.sources && m.sources.length > 0 && (
                  <div className="sources-card">
                    <div className="sources-header">Sources ({m.sources.length})</div>
                    {m.sources.map((src, i) => (
                      <div key={i} style={{ fontSize: '0.78rem', marginTop: '6px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span>📄 {src.filename} (Score: {(src.score * 100).toFixed(0)}%)</span>
                        {src.openable && (
                          <a href={`/file/${src.doc_id}`} target="_blank" rel="noopener noreferrer" className="doc-open">
                            Open ↗
                          </a>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))
        )}

        {isThinking && (
          <div className="message-row ai">
            <div className="message-bubble" style={{ color: 'var(--text-muted)' }}>
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
          />
          <button type="submit" className="send-pill-btn" disabled={!input.trim() || isThinking}>
            ➤
          </button>
        </form>
      </div>
    </main>
  );
}

/* ── Root App Component ──────────────────────────────────────── */
function App() {
  const [backendMode, setBackendMode] = useState('');
  const [retrievalMode, setRetrievalMode] = useState('hybrid');
  const [files, setFiles] = useState([]);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [strategy, setStrategy] = useState('structured');
  const [messages, setMessages] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isThinking, setIsThinking] = useState(false);

  const fetchStatus = useCallback(async () => {
    try {
      const status = await api.getStatus();
      setFiles(status.documents || []);
      if (status.vector_backend) setBackendMode(status.vector_backend);
      if (status.mode) setRetrievalMode(status.mode);
    } catch (err) {
      console.error("Failed to fetch status:", err);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  const handleUpload = async (fileList) => {
    setIsUploading(true);
    const formData = new FormData();
    fileList.forEach((f) => formData.append('files', f));
    formData.append('chunk_mode', strategy);

    try {
      const res = await api.uploadFiles(formData);
      if (res.ok) {
        setSelectedFiles([]);
        await fetchStatus();
      } else {
        alert(res.error || 'Upload failed');
      }
    } catch (err) {
      alert('Upload failed: ' + err.message);
    } finally {
      setIsUploading(false);
    }
  };

  const handleLoadUrl = async (url) => {
    const res = await api.loadUrl(url, strategy);
    if (res.ok) {
      await fetchStatus();
    } else {
      alert(res.error || 'Failed to load URL');
    }
  };

  const handleRemoveDoc = async (doc_id) => {
    await api.removeDoc(doc_id);
    await fetchStatus();
  };

  const handleClear = async () => {
    await api.clearSession();
    setMessages([]);
    await fetchStatus();
  };

  const handleSend = async (query) => {
    const userMsg = { role: 'user', text: query };
    setMessages((prev) => [...prev, userMsg]);
    setIsThinking(true);

    try {
      const res = await api.askQuestion(query, strategy);
      const aiMsg = {
        role: 'ai',
        text: res.answer || "I don't know.",
        sources: res.sources || []
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: 'ai', text: 'Error executing query: ' + err.message }
      ]);
    } finally {
      setIsThinking(false);
    }
  };

  return (
    <div className="layout">
      <Topbar backendMode={backendMode} docsCount={files.length} retrievalMode={retrievalMode} />
      <Sidebar
        strategy={strategy}
        setStrategy={setStrategy}
        files={files}
        onUpload={handleUpload}
        onLoadUrl={handleLoadUrl}
        onRemoveDoc={handleRemoveDoc}
        onClear={handleClear}
        isUploading={isUploading}
        selectedFiles={selectedFiles}
        setSelectedFiles={setSelectedFiles}
      />
      <ChatArea
        messages={messages}
        onSend={handleSend}
        isThinking={isThinking}
        filesCount={files.length}
        selectedFilesCount={selectedFiles.length}
      />
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
