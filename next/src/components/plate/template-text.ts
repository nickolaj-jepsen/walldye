/**
 * The var template files plates draw, fetched once per page through retrying() and shared by every
 * plate that shows them. An inlined template (TemplateInfo.inline) keeps its text; for any other
 * the fetch only warms the HTTP cache its external `<use>` reads, and tells a failed load apart.
 */
import { useEffect, useSyncExternalStore } from 'react';
import { retrying } from '../../client/retry';
import { templateUrl } from '../../lib/catalog';

/** A template file that has loaded. */
export interface LoadedTemplate {
  /** The file's address; after a failed try it carries `?r=<try>` so no engine reuses the failure. */
  url: string;
  /** The inlinable body of an inlined template; '' for one an external `<use>` draws. */
  text: string;
}

const loaded = new Map<string, LoadedTemplate>();
const loading = new Set<string>();
const listeners = new Set<() => void>();

function subscribe(onChange: () => void): () => void {
  listeners.add(onChange);
  return () => listeners.delete(onChange);
}

/** The file's children, without its root `<svg>`: what goes inside the plate's `<defs>`. */
function body(svg: string): string {
  return svg.slice(svg.indexOf('>') + 1, svg.lastIndexOf('</svg>'));
}

function load(hash: string, inline: boolean): void {
  if (loaded.has(hash) || loading.has(hash)) return;
  loading.add(hash);
  let tries = 0;
  retrying(async () => {
    const url = tries++ === 0 ? templateUrl(hash) : `${templateUrl(hash)}?r=${tries - 1}`;
    const r = await fetch(url);
    if (!r.ok) throw new Error(`${r.status}`);
    const svg = await r.text();
    loaded.set(hash, { url, text: inline ? body(svg) : '' });
    loading.delete(hash);
    for (const l of listeners) l();
  });
}

/** Template `hash` once its file has loaded, loading it on first use; undefined until then, and for null. */
export function useTemplateFile(hash: string | null, inline: boolean): LoadedTemplate | undefined {
  const file = useSyncExternalStore(
    subscribe,
    () => (hash ? loaded.get(hash) : undefined),
    () => undefined,
  );
  useEffect(() => {
    if (hash) load(hash, inline);
  }, [hash, inline]);
  return file;
}
