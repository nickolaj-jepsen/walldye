/** The catalogue's committed files as the tests read them. Not a test: neither runner matches this name. */
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { parse } from 'yaml';

/** Sorted names of every wallpapers/<slug>/ of `root` holding a meta.yaml. */
export function slugs(root: string): string[] {
  const dir = join(root, 'wallpapers');
  return readdirSync(dir)
    .filter((name) => existsSync(join(dir, name, 'meta.yaml')))
    .sort();
}

/** wallpapers/<slug>/meta.yaml parsed the way PyYAML's safe_load reads it ({} when empty). */
export function loadMeta(root: string, slug: string): Record<string, unknown> {
  const meta: unknown = parse(readFileSync(join(root, 'wallpapers', slug, 'meta.yaml'), 'utf8'), {
    version: '1.1',
    uniqueKeys: false,
  });
  return (meta ?? {}) as Record<string, unknown>;
}
