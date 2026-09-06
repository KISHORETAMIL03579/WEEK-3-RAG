import { marked } from 'marked';
import DOMPurify from 'dompurify';

/**
 * Safely parse Markdown text into sanitized HTML.
 * Uses marked for Markdown parsing and DOMPurify for strict sanitization,
 * preventing any XSS or hostile script injection.
 */
export function renderMarkdown(content?: string): { __html: string } {
  if (!content) {
    return { __html: '' };
  }
  try {
    const rawHtml = marked.parse(content) as string;
    const sanitizedHtml = DOMPurify.sanitize(rawHtml, {
      USE_PROFILES: { html: true },
      ADD_ATTR: ['target', 'rel'],
    });
    return { __html: sanitizedHtml };
  } catch {
    // Fallback plain text escaping if parsing fails
    const div = document.createElement('div');
    div.textContent = content;
    return { __html: div.innerHTML };
  }
}

