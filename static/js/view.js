const { useState, useEffect, useRef } = React;

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

    async function fetchPages() {
      try {
        const res = await fetch(`/file/${id}/pages`);
        const data = await res.json();
        if (!res.ok || !data.pages) {
          setError(data.error || 'Could not load document.');
        } else {
          setPages(data.pages);
          setFilename(data.filename || id);
          setExt(data.ext || 'pdf');
          if (initialPage > 0 && initialPage <= data.pages.length) {
            setCurPage(initialPage);
          }
        }
      } catch (err) {
        setError('Error fetching document: ' + err.message);
      } finally {
        setLoading(false);
      }
    }

    fetchPages();
  }, []);

  const handleSearch = (e) => {
    e.preventDefault();
    if (!searchQuery.trim() || pages.length === 0) return;

    let matchCount = 0;
    let firstPageMatch = -1;

    pages.forEach((p, idx) => {
      const re = new RegExp(searchQuery.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'ig');
      const matches = p.text.match(re);
      if (matches) {
        matchCount += matches.length;
        if (firstPageMatch === -1) firstPageMatch = idx + 1;
      }
    });

    setSearchCount(`${matchCount} matches found`);
    if (firstPageMatch !== -1) {
      setCurPage(firstPageMatch);
      setHighlightQuery(searchQuery);
    }
  };

  const highlightText = (text, query) => {
    if (!query) return text;
    const trimmed = query.trim();
    if (!trimmed) return text;
    const escaped = trimmed.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    // Chunk text is whitespace-normalized during ingestion (newlines and
    // repeated spaces collapsed to single spaces), but this raw page text
    // keeps its original line breaks — so a highlight snippet built from
    // chunk text would otherwise never match here at all. Treat any run
    // of literal spaces in the query as "any run of whitespace" so it
    // still finds its original (non-normalized) location on the page.
    const flexible = escaped.replace(/ +/g, '\\s+');
    let regex;
    try {
      regex = new RegExp(`(${flexible})`, 'gi');
    } catch {
      return text;
    }
    const parts = text.split(regex);
    // With exactly one capturing group, String.split places the matched
    // text at every odd index and surrounding non-matches at every even
    // index — reliable regardless of what the (whitespace-flexible) match
    // actually looked like, unlike comparing part === query by value.
    return parts.map((part, i) =>
      i % 2 === 1 ? (
        <mark key={i} style={{ background: 'var(--hl)', borderRadius: '2px', padding: '0 2px' }}>
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
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: 'var(--bg)' }}>
      {/* Header Bar */}
      <header className="app-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button className="nav-link" onClick={() => window.history.back()}>
            ← Back
          </button>
          <div className="brand">
            <span style={{ fontSize: '1rem' }}>📄</span>
            <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>{filename || 'Document Viewer'}</span>
          </div>
        </div>

        {/* Page Controls */}
        {!isPdf && pages.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'var(--bg-raised)', padding: '4px 12px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border)' }}>
            <button
              onClick={() => setCurPage((p) => Math.max(1, p - 1))}
              disabled={curPage <= 1}
              style={{ background: 'none', border: 'none', color: 'var(--text-primary)', cursor: 'pointer' }}
            >
              ←
            </button>
            <span style={{ fontFamily: 'var(--mono)', fontSize: '0.8rem' }}>
              Page {curPage} of {pages.length}
            </span>
            <button
              onClick={() => setCurPage((p) => Math.min(pages.length, p + 1))}
              disabled={curPage >= pages.length}
              style={{ background: 'none', border: 'none', color: 'var(--text-primary)', cursor: 'pointer' }}
            >
              →
            </button>
          </div>
        )}

        {/* Right Actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {!isPdf && (
            <form onSubmit={handleSearch} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <input
                type="text"
                placeholder="Search document..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{ fontSize: '0.8rem', padding: '4px 10px', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', color: '#fff' }}
              />
              {searchCount && <span style={{ fontSize: '0.75rem', color: 'var(--green)', fontFamily: 'var(--mono)' }}>{searchCount}</span>}
            </form>
          )}

          {/* Zoom Control */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'var(--bg-raised)', padding: '2px 8px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
            <button onClick={() => setZoom((z) => Math.max(0.5, z - 0.1))} style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer' }}>-</button>
            <span style={{ fontSize: '0.75rem', fontFamily: 'var(--mono)' }}>{Math.round(zoom * 100)}%</span>
            <button onClick={() => setZoom((z) => Math.min(2.0, z + 0.1))} style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer' }}>+</button>
          </div>

          <button onClick={() => window.close()} className="nav-link" style={{ color: 'var(--red)', background: 'var(--red-dim)' }}>
            ✕ Close
          </button>
        </div>
      </header>

      {/* Main Document Content Area */}
      <main style={{ flex: 1, overflowY: 'auto', padding: '24px', display: 'flex', justifyContent: 'center' }}>
        {loading && (
          <div style={{ margin: 'auto', color: 'var(--text-muted)' }}>Loading document pages...</div>
        )}

        {error && (
          <div style={{ margin: 'auto', color: 'var(--red)', background: 'var(--red-dim)', padding: '16px 24px', borderRadius: 'var(--radius-md)', border: '1px solid var(--red)' }}>
            {error}
          </div>
        )}

        {!loading && !error && isPdf && (
          <div style={{ width: '100%', maxWidth: '900px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {highlightQuery && (
              <div style={{
                background: 'var(--accent-glow)', border: '1px solid var(--accent)',
                borderRadius: 'var(--radius-md)', padding: '10px 16px', fontSize: '0.8rem',
                color: 'var(--text-primary)', lineHeight: 1.5,
              }}>
                {/* A plain <embed> for a PDF hands rendering straight to the
                    browser's own native PDF plugin — there's no API for us
                    to inject a highlight into that renderer's page content.
                    We CAN still jump to the right page (via the #page=N
                    fragment below); for finding the exact passage on that
                    page, showing what to look for is the honest fallback,
                    rather than silently doing nothing and looking broken. */}
                🔍 Looking for this passage (use your browser's Find, Ctrl/Cmd+F, if it's not immediately visible):
                <div style={{ marginTop: '4px', fontFamily: 'var(--mono)', fontSize: '0.76rem', color: 'var(--text-secondary)' }}>
                  "{highlightQuery}"
                </div>
              </div>
            )}
            <embed
              type="application/pdf"
              src={`/file/${docId}/raw#page=${curPage}`}
              style={{
                width: `${100 / zoom}%`,
                height: '80vh',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-md)',
                transform: `scale(${zoom})`,
                transformOrigin: 'top center'
              }}
            />
          </div>
        )}

        {!loading && !error && !isPdf && currentPageData && (
          <div
            className="doc-page"
            style={{
              transform: `scale(${zoom})`,
              transformOrigin: 'top center',
              maxWidth: '820px',
              width: '100%',
              background: 'hsl(220, 30%, 96%)',
              color: 'hsl(220, 30%, 14%)',
              padding: '36px',
              borderRadius: 'var(--radius-md)',
              boxShadow: 'var(--shadow-lg)',
              lineHeight: 1.7,
              whiteSpace: 'pre-wrap'
            }}
          >
            <div style={{ fontSize: '0.75rem', fontFamily: 'var(--mono)', color: '#666', borderBottom: '1px solid #ddd', paddingBottom: '8px', marginBottom: '16px', display: 'flex', justifyContent: 'space-between' }}>
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