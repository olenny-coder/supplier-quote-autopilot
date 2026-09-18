/**
 * Copy text to the clipboard.
 *
 * `navigator.clipboard` needs a secure context (https or localhost) and can
 * still be blocked by permissions policy, which matters here because the
 * Suppliers tab's "Copy link" is the primary way a buyer gets a private form
 * link out to a supplier. The legacy `execCommand` path keeps that working on
 * plain-http staging hosts and older browsers.
 *
 * Resolves to `true` when the copy succeeded so callers can toast accurately.
 */
export async function copyToClipboard(text) {
  if (!text) return false;

  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // Fall through to the legacy path.
  }

  try {
    const textarea = document.createElement("textarea");

    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.top = "-1000px";
    textarea.style.opacity = "0";

    document.body.appendChild(textarea);
    textarea.select();

    const succeeded = document.execCommand("copy");

    document.body.removeChild(textarea);

    return succeeded;
  } catch {
    return false;
  }
}
