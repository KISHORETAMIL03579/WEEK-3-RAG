const { useState, useEffect, useRef, useCallback } = React;

/* ── Safe Regex Escaping Helper ─────────────────────────────── */
function escapeRegex(str) {
  return (str || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function DocViewerApp() {
  const [docId, setDocId] = useState('');
  const [filename, setFilename] = useState(window.DOC_FILENAME || '');
  const [pages, setPages] = useState([]);
  const [curPage, setCurPage] = useState(1);
  const [zoom, setZoom] = useState(1);
  const [ext, setExt] = useState(window.DOC_EXT || 'pdf');
  const [searchQuery, setSearchQuery] = useState('');
  const [highlightQuery, setHighlightQuery] = useState('');
  const [searchCount, setSearchCount] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const id = params.get('doc_id') || window.DOC_ID || '';
    const initialPage = parseInt(params.get('page') || '1', 10);
    const initialHl = params.get('hl') || '';

    setDocId(id);
    if (initialHl) setHighlightQuery(initialHl);

    if (!id) {
      setError('No document ID specified.');
      setLoading(false);
      return;
    }

    const controller = new AbortController();

    async function fetchPages() {
      try {
        const safeId = encodeURIComponent(String(id));
        const res = await fetch(`/file/${safeId}/pages`, { signal: controller.signal });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(data.error || data.message || `Request failed with status ${res.status}`);
        }
        if (!Array.isArray(data.pages)) {
          throw new Error('Invalid document response format.');
        }
        setPages(data.pages);
        setFilename(data.filename || id);
        setExt(data.ext || 'pdf');
        if (initialPage > 0 && initialPage <= data.pages.length) {
          setCurPage(initialPage);
        }
      } catch (err) {
        if (err.name === 'AbortError') return;
        setError(err.message || 'Could not load document.');
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    fetchPages();

    return () => controller.abort();
  }, []);

  const handleBack = useCallback(() => {
    if (typeof window !== 'undefined' && window.history.length > 1) {
      window.history.back();
    } else {
      window.location.href = '/';
    }
  }, []);

  const handleClose = useCallback(() => {
    if (typeof window !== 'undefined') {
      window.close();
      setTimeout(() => {
        window.location.href = '/';
      }, 100);
    }
  }, []);

  const handleSearch = (e) => {
    e.preventDefault();
    const trimmed = searchQuery.trim();
    if (!trimmed || pages.length === 0) return;

    let matchCount = 0;
    let firstPageMatch = -1;
    const escaped = escapeRegex(trimmed);
    const re = new RegExp(escaped, 'ig');

    pages.forEach((p, idx) => {
      const pageText = typeof p?.text === 'string' ? p.text : '';
      const matches = pageText.match(re);
      if (matches) {
        matchCount += matches.length;
        if (firstPageMatch === -1) firstPageMatch = idx + 1;
      }
    });

    setSearchCount(`${matchCount} match${matchCount === 1 ? '' : 'es'} found`);
    if (firstPageMatch !== -1) {
      setCurPage(firstPageMatch);
      setHighlightQuery(trimmed);
    }
  };

  const highlightText = (text, query) => {
    const safeText = typeof text === 'string' ? text : '';
    if (!safeText) return safeText;
    if (!query) return safeText;
    const trimmed = query.trim();
    if (!trimmed) return safeText;
    const escaped = escapeRegex(trimmed);
    const flexible = escaped.replace(/ +/g, '\\s+');
    let regex;
    try {
      regex = new RegExp(`(${flexible})`, 'gi');
    } catch {
      return safeText;
    }
    const parts = safeText.split(regex);
    return parts.map((part, i) =>
      i % 2 === 1 ? (
        <mark key={i} className="doc-highlight-mark">
          {part}
        </mark>
      ) : (
        part
      )
    );
  };

  const isPdf = ext === 'pdf';
  const currentPageData = pages[curPage - 1];

  return (
    <div className="viewer-shell">
      {/* Header Bar */}
      <header className="app-header">
        <div className="viewer-header-left">
          <button type="button" className="nav-link" onClick={handleBack} title="Back to previous page or home">
            ← Back
          </button>
          <div className="brand">
            <span className="viewer-brand-icon">📄</span>
            <span className="viewer-brand-name">{filename || 'Document Viewer'}</span>
          </div>
        </div>

        {/* Page Controls */}
        {!isPdf && pages.length > 0 && (
          <div className="viewer-pagination-pill">
            <button
              type="button"
              className="viewer-icon-btn"
              onClick={() => setCurPage((p) => Math.max(1, p - 1))}
              disabled={curPage <= 1}
              aria-label="Previous page"
              title="Previous page"
            >
              ←
            </button>
            <span className="viewer-page-label">
              Page {curPage} of {pages.length}
            </span>
            <button
              type="button"
              className="viewer-icon-btn"
              onClick={() => setCurPage((p) => Math.min(pages.length, p + 1))}
              disabled={curPage >= pages.length}
              aria-label="Next page"
              title="Next page"
            >
              →
            </button>
          </div>
        )}

        {/* Right Actions */}
        <div className="viewer-header-right">
          {!isPdf && (
            <form onSubmit={handleSearch} className="viewer-search-form">
              <input
                type="text"
                placeholder="Search document..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="viewer-search-input"
                aria-label="Search within document"
              />
              {searchCount && <span className="viewer-search-count" aria-live="polite">{searchCount}</span>}
            </form>
          )}

          {/* Zoom Control */}
          <div className="viewer-zoom-pill">
            <button
              type="button"
              className="viewer-icon-btn"
              onClick={() => setZoom((z) => Math.max(0.5, parseFloat((z - 0.1).toFixed(1))))}
              title="Zoom out"
              aria-label="Zoom out"
            >
              −
            </button>
            <span className="viewer-zoom-label">{Math.round(zoom * 100)}%</span>
            <button
              type="button"
              className="viewer-icon-btn"
              onClick={() => setZoom((z) => Math.min(2.0, parseFloat((z + 0.1).toFixed(1))))}
              title="Zoom in"
              aria-label="Zoom in"
            >
              +
            </button>
          </div>

          <button
            type="button"
            onClick={handleClose}
            className="nav-link nav-link-danger"
            title="Close viewer"
            aria-label="Close viewer"
          >
            ✕ Close
          </button>
        </div>
      </header>

      {/* Main Document Content Area */}
      <main className="viewer-main">
        {loading && (
          <div className="viewer-loading">Loading document pages...</div>
        )}

        {error && (
          <div className="viewer-error">
            {error}
          </div>
        )}

        {!loading && !error && isPdf && (
          <div className="viewer-pdf-wrapper">
            {highlightQuery && (
              <div className="viewer-pdf-notice">
                🔍 Looking for this passage (use your browser's Find, Ctrl/Cmd+F, if it's not immediately visible):
                <div className="viewer-pdf-snippet">
                  "{highlightQuery}"
                </div>
              </div>
            )}
            <embed
              type="application/pdf"
              src={`/file/${encodeURIComponent(String(docId))}/raw#page=${curPage}`}
              className="viewer-pdf-embed"
              style={{ '--viewer-zoom': zoom }}
            />
          </div>
        )}

        {!loading && !error && !isPdf && currentPageData && (
          <div
            className="viewer-doc-page"
            style={{ '--viewer-zoom': zoom }}
          >
            <div className="viewer-doc-meta">
              <span>Section {currentPageData.num} of {pages.length}</span>
              <span>{filename}</span>
            </div>
            <div>{highlightText(currentPageData.text, highlightQuery)}</div>
          </div>
        )}
      </main>
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<DocViewerApp />);