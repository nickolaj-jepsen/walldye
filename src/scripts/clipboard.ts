/** Copying text for the "Copy link" and "Copy" buttons. */

/** Puts `text` on the clipboard; resolves false when the browser refuses. */
export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // No async clipboard (insecure context, older engine): the selection-based fallback.
  }
  const area = document.createElement('textarea');
  area.value = text;
  area.setAttribute('readonly', '');
  area.style.position = 'fixed';
  area.style.opacity = '0';
  document.body.append(area);
  area.select();
  let ok = false;
  try {
    ok = document.execCommand('copy');
  } catch {
    ok = false;
  }
  area.remove();
  return ok;
}

const restore = new WeakMap<HTMLElement, number>();

/** Shows `text` on `button` for two seconds, then its own label again. */
export function flash(button: HTMLElement, text: string): void {
  const label = button.dataset.label ?? button.textContent ?? '';
  button.dataset.label = label;
  button.textContent = text;
  clearTimeout(restore.get(button));
  restore.set(
    button,
    window.setTimeout(() => {
      button.textContent = label;
    }, 2000),
  );
}
