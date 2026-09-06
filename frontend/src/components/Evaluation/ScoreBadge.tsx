import React from 'react';

interface ScoreBadgeProps {
  pct: number;
}

export const ScoreBadge: React.FC<ScoreBadgeProps> = ({ pct }) => {
  let style: React.CSSProperties = {
    background: 'var(--red-bg, rgba(239, 68, 68, 0.12))',
    border: '1px solid var(--red-border, rgba(239, 68, 68, 0.25))',
    color: 'var(--red-text, #ef4444)',
  };

  if (pct >= 80) {
    style = {
      background: 'var(--green-bg, rgba(16, 185, 129, 0.12))',
      border: '1px solid var(--green-border, rgba(16, 185, 129, 0.25))',
      color: 'var(--green-text, #10b981)',
    };
  } else if (pct >= 50) {
    style = {
      background: 'var(--amber-bg, rgba(245, 158, 11, 0.12))',
      border: '1px solid var(--amber-border, rgba(245, 158, 11, 0.25))',
      color: 'var(--amber-text, #f59e0b)',
    };
  }

  return (
    <span className="score-pill" style={style}>
      {pct}%
    </span>
  );
};

