/**
 * Copy text to clipboard — works on HTTP and HTTPS.
 * Tries execCommand first (sync, works in click handlers on HTTP),
 * then Clipboard API, then legacy fallback.
 */
export function copyToClipboard(text) {
  if (!text) return Promise.resolve(false);

  // Method 1: Synchronous execCommand — most reliable in click handlers on HTTP
  try {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    // Must be visible to iOS Safari — use offscreen but not display:none
    ta.style.cssText = 'position:fixed;left:-9999px;top:-9999px;opacity:0;';
    document.body.appendChild(ta);

    // iOS Safari needs special range selection
    if (navigator.userAgent.match(/ipad|iphone/i)) {
      const range = document.createRange();
      range.selectNodeContents(ta);
      const sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
      ta.setSelectionRange(0, text.length);
    } else {
      ta.select();
    }

    const ok = document.execCommand('copy');
    document.body.removeChild(ta);
    if (ok) return Promise.resolve(true);
  } catch {
    // fall through
  }

  // Method 2: Async Clipboard API (requires HTTPS or localhost, but try anyway)
  if (navigator.clipboard) {
    return navigator.clipboard.writeText(text).then(() => true).catch(() => false);
  }

  return Promise.resolve(false);
}
