/**
 * Copy text to clipboard — works on HTTP and HTTPS, inside dialogs and dropdowns.
 *
 * Tries Clipboard API first (works in dialogs without focus issues),
 * then falls back to execCommand with a textarea (works on HTTP).
 * Uses setTimeout to escape Radix UI focus traps in dropdowns.
 */
export function copyToClipboard(text) {
  if (!text) return Promise.resolve(false);

  return new Promise((resolve) => {
    // Small delay to escape Radix DropdownMenu/Dialog focus traps
    setTimeout(async () => {
      // Method 1: Clipboard API — works inside dialogs (no focus needed)
      if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
        try {
          await navigator.clipboard.writeText(text);
          resolve(true);
          return;
        } catch {
          // Clipboard API can fail on HTTP — fall through to execCommand
        }
      }

      // Method 2: execCommand with textarea — works on HTTP
      try {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.setAttribute('readonly', '');
        ta.style.cssText =
          'position:fixed;left:-9999px;top:-9999px;width:1px;height:1px;padding:0;border:none;outline:none;box-shadow:none;background:transparent;opacity:0;';
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

      // Method 3: window.clipboardData (IE/legacy)
      if (window.clipboardData && window.clipboardData.setData) {
        try {
          window.clipboardData.setData('Text', text);
          resolve(true);
          return;
        } catch {
          // fall through
        }
      }

      resolve(false);
    }, 50);
  });
}
