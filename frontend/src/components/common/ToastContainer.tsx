import React from 'react';

export interface ToastItem {
  id: string;
  message: string;
  type?: 'info' | 'success' | 'error';
}

interface ToastContainerProps {
  toasts: ToastItem[];
  onDismiss: (id: string) => void;
}

export const ToastContainer: React.FC<ToastContainerProps> = ({ toasts, onDismiss }) => {
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
};

