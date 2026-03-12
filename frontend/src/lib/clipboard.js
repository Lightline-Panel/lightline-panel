/**
 * Copy text to clipboard — optimized for mobile (iOS Safari, Android Chrome).
 *
 * MUST be called synchronously from a user gesture (click/tap handler).
 * No setTimeout — that breaks the "user activation" requirement on mobile.
 *
 * Fallback chain:
 *  1. navigator.clipboard.writeText (HTTPS only, needs user gesture)
 *  2. execCommand('copy') with <textarea> (works on HTTP, iOS needs special selection)
 *  3. Prompt user to manually copy (last resort)
 */
export async function copyToClipboard(text) {
  if (!text) return false;

  // Method 1: Modern Clipboard API (HTTPS + user gesture required)
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // Falls through — permission denied or not in user gesture
    }
  }

  // Method 2: execCommand with textarea — works on HTTP & inside dialogs
  try {
    const ok = _execCopy(text);
    if (ok) return true;
  } catch {
    // fall through
  }

  // Method 3: window.clipboardData (IE/legacy Edge)
  if (window.clipboardData && window.clipboardData.setData) {
    try {
      window.clipboardData.setData('Text', text);
      return true;
    } catch {
      // fall through
    }
  }

  return false;
}

/**
 * execCommand copy using a temporary textarea.
 * Handles iOS Safari quirks (contentEditable + setSelectionRange).
 */
function _execCopy(text) {
  const isIOS = /ipad|iphone|ipod/i.test(navigator.userAgent) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);

  const el = document.createElement('textarea');
  el.value = text;
  el.setAttribute('readonly', '');
  // Must be visible to iOS — opacity:0 and clip it instead of moving offscreen
  el.style.cssText = [
    'position:fixed',
    'top:50%',
    'left:50%',
    'width:1px',
    'height:1px',
    'padding:0',
    'border:none',
    'outline:none',
    'box-shadow:none',
    'background:transparent',
    'color:transparent',
    'font-size:16px',       // prevents iOS zoom on focus
    'clip:rect(0,0,0,0)',
    'white-space:pre',
    '-webkit-text-size-adjust:none',
  ].join(';');

  document.body.appendChild(el);

  let ok = false;
  try {
    if (isIOS) {
      // iOS requires contentEditable + setSelectionRange
      el.contentEditable = true;
      el.readOnly = false;
      const range = document.createRange();
      range.selectNodeContents(el);
      const sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
      el.setSelectionRange(0, 999999);
    } else {
      el.focus({ preventScroll: true });
      el.select();
    }
    ok = document.execCommand('copy');
  } catch {
    ok = false;
  }
  document.body.removeChild(el);
  return ok;
}
