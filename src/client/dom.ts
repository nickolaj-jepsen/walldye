/** Reading the hooks the server-rendered pages give the client (DOM.md). */

/** The first element under `root` matching `selector`; throws when there is none, so a missing hook fails loudly. */
export function must<T extends Element = HTMLElement>(
  selector: string,
  root: ParentNode = document,
): T {
  const el = root.querySelector<T>(selector);
  if (!el) throw new Error(`missing ${selector}`);
  return el;
}

/** `el.dataset[key]` parsed as JSON, or `fallback` when it is absent or malformed. */
export function readJson<T>(el: HTMLElement, key: string, fallback: T): T {
  const text = el.dataset[key];
  if (text === undefined) return fallback;
  try {
    return JSON.parse(text) as T;
  } catch {
    return fallback;
  }
}

/** A form's entries as query parameters, the form's own GET serialization. */
export function formParams(form: HTMLFormElement): URLSearchParams {
  return new URLSearchParams([...new FormData(form)].map(([k, v]) => [k, String(v)]));
}

/** Replaces the address with `url` when it differs, keeping the history entry and its state. */
export function replaceAddress(url: URL): void {
  if (url.href !== location.href) history.replaceState(history.state, '', url.href);
}
