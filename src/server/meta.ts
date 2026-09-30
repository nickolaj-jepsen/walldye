/**
 * Rules over a parsed meta.yaml shared by CI and the content schema: the license default and draft
 * flag (ports of walldye/tools/lint/piece.py license_of and metadata.is_draft) and the `variants:`
 * mapping. The copy rules live in walldye/tools/lint/words.py.
 */

import { z } from 'astro/zod';
import { DEFAULT_VARIANT } from '../lib/content';

export const DEFAULT_LICENSE = 'CC0-1.0';
export const FAN_WORK = 'LicenseRef-fan-work';
/** Named variants per design, so at most 5 versions with the default. */
export const MAX_VARIANTS = 4;
export const MAX_LABEL_WORDS = 4;
const MAX_VARIANT_NAME = 24;
/** A variant name: lowercase words joined by single hyphens, so `<slug>--<name>` splits back. */
export const VARIANT_NAME = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

type Meta = Record<string, unknown>;

const words = (text: string): number => text.split(/\s+/).filter(Boolean).length;

/** Slugs that would shadow a site route or file (walldye/tools/lint/piece.py RESERVED_SLUGS). */
export const RESERVED_SLUGS: ReadonlySet<string> = new Set([
  'about',
  'index',
  't',
  'og',
  'fonts',
  '404',
  'robots',
  'favicon',
]);

/** Whether a slug collides with a site route or file: RESERVED_SLUGS, `sitemap*` or `_*`. */
export function reservedSlug(slug: string): boolean {
  return RESERVED_SLUGS.has(slug) || slug.startsWith('sitemap') || slug.startsWith('_');
}

/** Whether `meta` marks its piece a draft: only `draft: true` does. */
export function isDraft(meta: Meta): boolean {
  return meta.draft === true;
}

const variantEntry = z
  .object({
    /** Names the version in the detail page's switcher. */
    label: z.string().trim().min(1),
    /** Replaces the piece's description while this version is shown; named variants only. */
    description: z.string().trim().min(1).optional(),
    /** Replaces the piece's alt text while this version is shown; named variants only. */
    alt: z.string().trim().min(1).optional(),
    /** Built but hidden from the production site; named variants only. */
    draft: z.boolean().optional(),
  })
  .strict();

/**
 * meta.yaml `variants:`: `default` plus every named variant design.py declares, each with a label of
 * at most MAX_LABEL_WORDS words, unique within the piece. At most MAX_VARIANTS named variants;
 * `description`, `alt` and `draft` belong to named variants only. Whether the names match design.py is
 * `walldye check`'s to say.
 */
export const variantsMeta = z.record(z.string(), variantEntry).superRefine((vs, ctx) => {
  const issue = (message: string, path: string[] = []) =>
    ctx.addIssue({ code: 'custom', message, path });
  const names = Object.keys(vs).filter((k) => k !== DEFAULT_VARIANT);
  const unnamed = vs[DEFAULT_VARIANT];
  if (!unnamed)
    issue('needs a default entry, the label of the version design.py draws without a variant');
  if (!names.length) issue('lists no named variants; leave variants: out');
  if (names.length > MAX_VARIANTS)
    issue(`at most ${MAX_VARIANTS} named variants, got ${names.length}`);
  for (const name of names) {
    if (!VARIANT_NAME.test(name) || name.length > MAX_VARIANT_NAME) {
      issue(
        `${name} is not a variant name: lowercase words joined by single hyphens, at most ${MAX_VARIANT_NAME} characters`,
        [name],
      );
    }
  }
  if (unnamed?.description !== undefined)
    issue('the default version shows the piece description', [DEFAULT_VARIANT, 'description']);
  if (unnamed?.alt !== undefined)
    issue('the default version shows the piece alt text', [DEFAULT_VARIANT, 'alt']);
  if (unnamed?.draft !== undefined)
    issue('the default version is a draft only with the piece', [DEFAULT_VARIANT, 'draft']);
  const seen = new Map<string, string>();
  for (const [name, v] of Object.entries(vs)) {
    const n = words(v.label);
    if (n > MAX_LABEL_WORDS)
      issue(`label has ${n} words, over ${MAX_LABEL_WORDS}`, [name, 'label']);
    const key = v.label.toLowerCase();
    const other = seen.get(key);
    if (other !== undefined) issue(`label repeats the label of ${other}`, [name, 'label']);
    else seen.set(key, name);
  }
});

export interface NamedVariant {
  name: string;
  label: unknown;
  description: unknown;
  alt: unknown;
  draft: boolean;
}

const isMapping = (v: unknown): v is Meta =>
  typeof v === 'object' && v !== null && !Array.isArray(v);

/**
 * The named variants under meta.yaml `variants:`, in file order, read without validating them
 * (variantsMeta reports what is wrong) and leaving out entries that are not mappings, as
 * walldye/tools/metadata.py meta_variants does; [] when the key is absent or not a mapping.
 */
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
 * piece a model made (`model:`) with no recreation source, else null.
 */
export function licenseOf(meta: Meta): unknown {
  if (meta.license) return meta.license;
  if ('franchise' in meta) return FAN_WORK;
  const sources = Array.isArray(meta.sources) ? meta.sources : [];
  const recreation = sources.some(
    (s) => typeof s === 'object' && s !== null && (s as Meta).kind === 'recreation',
  );
  return meta.model && !recreation ? DEFAULT_LICENSE : null;
}
