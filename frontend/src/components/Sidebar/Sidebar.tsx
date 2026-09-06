import React, { useState, useEffect, useRef } from 'react';
import { DocumentInfo, StagedFile } from '../../types/document';
import { getTempClass, getTempLabel } from '../../utils/helpers';

interface SidebarProps {
  strategy: string;
  setStrategy: (strategy: string) => void;
  setStrategySelected: (selected: boolean) => void;
  topK: number;
  setTopK: React.Dispatch<React.SetStateAction<number>>;
  temperature: number;
  setTemperature: React.Dispatch<React.SetStateAction<number>>;
  files: DocumentInfo[];
  onUpload: (files: StagedFile[]) => void;
  onLoadUrl: (url: string) => Promise<void>;
  onRemoveDoc: (docId: string) => void;
  onClear: () => void;
  isUploading: boolean;
  isThinking: boolean;
  selectedFiles: StagedFile[];
  onAddSelectedFiles: (rawFiles: File[]) => void;
  onRemoveSelectedFile: (id: string) => void;
  onClearSelectedFiles: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
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
  onClearSelectedFiles,
}) => {
  const [dragActive, setDragActive] = useState(false);
  const [urlInput, setUrlInput] = useState('');
  const [isLoadingUrl, setIsLoadingUrl] = useState(false);
  const [showCompare, setShowCompare] = useState(false);
  const [topKInput, setTopKInput] = useState(String(topK));
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setTopKInput(String(topK));
  }, [topK]);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (isThinking || isUploading) return;
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true);
    else if (e.type === 'dragleave') setDragActive(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (isThinking || isUploading) return;
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      onAddSelectedFiles(Array.from(e.dataTransfer.files));
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      onAddSelectedFiles(Array.from(e.target.files));
      e.target.value = '';
    }
  };

  const handleUrlSubmit = async (e: React.FormEvent) => {
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

  const handleTopKInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
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

        {/* Selected Queued Staged Files List */}
        {isReadyToUpload && (
          <div className="staged-files-list">
            <div className="staged-files-header">Files queued to index:</div>
            {selectedFiles.map((f) => (
              <div key={f.id} className="staged-file-item">
                <span className="doc-name" title={f.name}>
                  📄 {f.name}
                </span>
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
            setStrategySelected(true);
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
          <div className="doc-empty-state">No documents loaded</div>
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
};

