import React, { useState, useEffect, useRef } from 'react';
import { SourceInfo } from '../../types/api';
import { SourceItem } from '../Sources/SourceItem';
import { renderMarkdown } from '../../utils/markdown';

export interface ChatMessage {
  id: string;
  role: 'user' | 'ai';
  text: string;
  sources?: SourceInfo[];
  query?: string;
  topK?: number;
  temperature?: number;
}

interface ChatAreaProps {
  messages: ChatMessage[];
  onSend: (query: string) => void;
  isThinking: boolean;
  filesCount: number;
  selectedFilesCount: number;
  strategy: string;
  strategySelected: boolean;
}

export const ChatArea: React.FC<ChatAreaProps> = ({
  messages,
  onSend,
  isThinking,
  filesCount,
  selectedFilesCount,
  strategy,
  strategySelected,
}) => {
  const [input, setInput] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isThinking]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const query = input.trim();
    if (!query || isThinking) return;
    onSend(query);
    setInput('');
  };

  /* ── Sequential Onboarding State Machine ─────── */
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
                {m.role === 'ai' ? (
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
                    <span className="meta-pill">
                      🌡️ Temp: {m.temperature != null ? Number(m.temperature).toFixed(2) : '0.00'}
                    </span>
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
};

