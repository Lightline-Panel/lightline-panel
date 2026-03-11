/**
 * Copy text to clipboard with fallback for non-HTTPS contexts.
 * navigator.clipboard.writeText requires a secure context (HTTPS or localhost).
 * The fallback uses a temporary textarea element.
 */
export async function copyToClipboard(text) {
  if (!text) return false;

  // Method 1: Modern Clipboard API (requires HTTPS or localhost)
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // fall through to fallback
    }
  }

  // Method 2: Fallback using textarea + execCommand (works on HTTP)
  try {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'fixed';
    textarea.style.left = '0';
    textarea.style.top = '0';
    textarea.style.width = '2em';
    textarea.style.height = '2em';
    textarea.style.padding = '0';
    textarea.style.border = 'none';
    textarea.style.outline = 'none';
    textarea.style.boxShadow = 'none';
    textarea.style.background = 'transparent';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();

    let ok = false;
    try {
      ok = document.execCommand('copy');
    } catch {
      ok = false;
    }
    document.body.removeChild(textarea);
    if (ok) return true;
  } catch {
    // fall through
  }

  // Method 3: window.clipboardData (IE/Edge legacy)
  try {
    if (window.clipboardData && window.clipboardData.setData) {
      window.clipboardData.setData('Text', text);
      return true;
    }
  } catch {
    // ignore
  }

  return false;
}
