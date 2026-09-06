import React, { useState } from 'react';
import { SourceInfo } from '../../types/api';

interface SourceItemProps {
  src: SourceInfo;
  index: number;
}

export const SourceItem: React.FC<SourceItemProps> = ({ src, index }) => {
  const [expanded, setExpanded] = useState(false);
  const scorePct = Math.max(0, Math.min(100, Math.round((src.score || 0) * 100)));
  const scoreClass = scorePct >= 80 ? 'score-high' : scorePct >= 60 ? 'score-mid' : 'score-low';

  const openHref = (() => {
    const params = new URLSearchParams();
    if (src.page) params.set('page', String(src.page));
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
        {src.openable !== false && (
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
};

