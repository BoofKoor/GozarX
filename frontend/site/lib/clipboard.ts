// Copy text to the clipboard with a webview-safe fallback. `navigator.clipboard` is undefined in
// non-secure contexts and in several Android in-app WebViews — most importantly Telegram's, which is
// the dominant referral channel here — so a bare `navigator.clipboard.writeText` silently fails there
// and the user's "copy" tap does nothing. Fall back to a hidden textarea + execCommand("copy"), which
// still works in those WebViews. Returns whether the copy actually succeeded so callers can show a
// real error state instead of a fake "copied!" toast.
export async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // fall through to the legacy path (permissions/secure-context refusal)
  }
  return legacyCopy(text);
}

function legacyCopy(text: string): boolean {
  if (typeof document === "undefined") return false;
  const ta = document.createElement("textarea");
  ta.value = text;
  // Keep it off-screen but still selectable; readOnly avoids the mobile keyboard popping up.
  ta.setAttribute("readonly", "");
  ta.style.position = "fixed";
  ta.style.top = "-9999px";
  ta.style.opacity = "0";
  document.body.appendChild(ta);
  try {
    ta.select();
    ta.setSelectionRange(0, text.length);
    return document.execCommand("copy");
  } catch {
    return false;
  } finally {
    document.body.removeChild(ta);
  }
}
