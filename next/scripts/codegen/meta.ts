/**
 * The meta.yaml rules codegen needs, from the Astro site's src/server/meta.ts without its schema:
 * the license default, the draft flag and the named variants. `walldye check` owns validation.
 */

export const DEFAULT_LICENSE = 'CC0-1.0';
export const FAN_WORK = 'LicenseRef-fan-work';
export const DEFAULT_VARIANT = 'default';

export type Meta = Record<string, unknown>;

export const isMapping = (v: unknown): v is Meta =>
  typeof v === 'object' && v !== null && !Array.isArray(v);

/** Whether `meta` marks its piece a draft: only `draft: true` does. */
export function isDraft(meta: Meta): boolean {
  return meta.draft === true;
}

export interface NamedVariant {
  name: string;
  label: unknown;
  description: unknown;
  alt: unknown;
  draft: boolean;
}

/** The named variants under `variants:`, in file order, leaving out entries that are not mappings; [] without the key. */
export function namedVariants(meta: Meta): NamedVariant[] {
  const vs = meta.variants;
  if (!isMapping(vs)) return [];
  return Object.entries(vs)
    .filter((e): e is [string, Meta] => e[0] !== DEFAULT_VARIANT && isMapping(e[1]))
    .map(([name, e]) => ({
      name,
      label: e.label,
      description: e.description,
      alt: e.alt,
      draft: isDraft(e),
    }));
}

/**
 * The folder's license: `license:`, else FAN_WORK when `franchise:` is set, else DEFAULT_LICENSE for a
 * piece a model made with no recreation source, else null.
 */
export function licenseOf(meta: Meta): unknown {
  if (meta.license) return meta.license;
  if ('franchise' in meta) return FAN_WORK;
  const sources = Array.isArray(meta.sources) ? meta.sources : [];
  const recreation = sources.some((s) => isMapping(s) && s.kind === 'recreation');
  return meta.model && !recreation ? DEFAULT_LICENSE : null;
}
