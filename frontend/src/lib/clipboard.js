/**
 * Copy text to clipboard — works on HTTP and HTTPS.
 *
 * Uses a short setTimeout to escape Radix UI dropdown focus traps,
 * then tries execCommand (works on HTTP) and Clipboard API (HTTPS).
 */
export function copyToClipboard(text) {
  if (!text) return Promise.resolve(false);

  return new Promise((resolve) => {
    // Delay to let Radix DropdownMenu fully close and release focus.
    // Without this, execCommand('copy') silently fails inside dropdown handlers.
    setTimeout(() => {
      // Method 1: execCommand with textarea — works on HTTP
      try {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.setAttribute('readonly', '');
        ta.style.cssText =
          'position:fixed;left:0;top:0;width:1px;height:1px;padding:0;border:none;outline:none;box-shadow:none;background:transparent;opacity:0.01;';
        document.body.appendChild(ta);

        if (/ipad|iphone/i.test(navigator.userAgent)) {
          const range = document.createRange();
          range.selectNodeContents(ta);
          const sel = window.getSelection();
          sel.removeAllRanges();
          sel.addRange(range);
          ta.setSelectionRange(0, text.length);
        } else {
          ta.focus({ preventScroll: true });
          ta.select();
        }

        const ok = document.execCommand('copy');
        document.body.removeChild(ta);
        if (ok) { resolve(true); return; }
      } catch {
        // fall through
      }

      // Method 2: Clipboard API (requires HTTPS or localhost)
      if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
        navigator.clipboard.writeText(text).then(() => resolve(true)).catch(() => resolve(false));
        return;
      }

      resolve(false);
    }, 100);
  });
}
