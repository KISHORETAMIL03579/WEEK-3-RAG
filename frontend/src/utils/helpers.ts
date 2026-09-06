export function generateId(prefix = 'id'): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export function getTempClass(t: number): string {
  if (t === 0) return 'zero';
  if (t <= 0.3) return 'low';
  if (t <= 0.7) return 'mid';
  return 'high';
}

export function getTempLabel(t: number): string {
  if (t === 0) return 'Deterministic';
  if (t <= 0.3) return 'Grounded';
  if (t <= 0.7) return 'Balanced';
  return 'Hallucination Risk';
}

export function escapeRegex(str: string): string {
  return (str || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

