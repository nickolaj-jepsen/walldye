/** The wallpapers collection's schema: meta.yaml in the shape the pages read, plus what the loader attaches. */
import { z } from 'astro/zod';
import { LICENSE_LINES, type TaxonomyFacet } from '../../lib/labels';
import { DEFAULT_LICENSE, FAN_WORK, reservedSlug, variantsMeta } from '../meta';
import { TAXONOMY } from '../taxonomy';

const SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

const facetList = (facet: TaxonomyFacet) =>
  z
    .array(z.string())
    .default([])
    .superRefine((vs, ctx) => {
      for (const v of vs) {
        if (!(v in TAXONOMY.facets[facet]))
          ctx.addIssue({
            code: 'custom',
            message: `${v} is not in taxonomy.yaml (suggest it under proposed_facets)`,
          });
      }
    });

const source = z
  .object({
    kind: z.enum(['recreation', 'inspiration', 'reference', 'data']),
    /** The name of a work, set in italics. */
    title: z.string().min(1).optional(),
    /** The name of anything that is not a work (a technique, place, product or thing), set upright. */
    topic: z.string().min(1).optional(),
    author: z.string().min(1).optional(),
    year: z.union([z.number().int(), z.string().min(1)]).optional(),
    url: z.url().optional(),
    /** BCP 47 language of a foreign title or topic, set on its element. */
    lang: z.string().min(2).optional(),
  })
  .strict()
  .refine((s) => !(s.title && s.topic), {
    message: 'a title names a work and a topic anything else; not both',
  })
  .refine((s) => s.title || s.topic || s.author, {
    message: 'a source needs a title, a topic or an author',
  });

export const template = z.object({
  /** File name inside its build directory. */
  file: z.string(),
  /** Path of the file from the project root. */
  path: z.string(),
  /** servedHash of the file. */
  hash: z.string(),
  /** Served copy: servedUrl(hash, 'svg'). */
  url: z.string(),
});

/** What the loader reads from one build directory: build/ for the default, build/<variant>/ for a named variant. */
export const build = {
  /** Templates by slots.json key, `<aspect>/<regime>`. */
  templates: z.record(z.string(), template),
  /** servedHash of the slots.json. */
  slotsHash: z.string(),
  /** Served copy of the slots.json: servedUrl(slotsHash, 'slots.json'). */
  slotsUrl: z.string(),
  /** Path of the slots.json from the project root. */
  slotsPath: z.string(),
  /** Ink-weighted centroid of the 16:9 template, each 0..1. */
  focus: z.tuple([z.number(), z.number()]),
};

/** One version of a piece: the default or a named variant, with its meta.yaml copy and its build. */
export const version = z
  .object({
    /** `default` or the variant name. */
    name: z.string(),
    label: z.string(),
    /** The variant's own description, else the piece's. */
    description: z.string(),
    /** The variant's own alt text, else the piece's. */
    alt: z.string(),
    draft: z.boolean(),
    ...build,
  })
  .strict();

/**
 * One wallpaper: meta.yaml in the shape the pages read, plus what the loader attaches from the
 * folder. walldye check owns the rest of the meta.yaml rules; this keeps only what a page needs to
 * render: facet values, credit and license words the site has, and a slug that is a free route.
 */
export const wallpaper = z
  .object({
    title: z.string().trim().min(1),
    description: z.string().trim().min(1),
    /** What the picture shows, for the plate's alt text. */
    alt: z.string().trim().min(1),
    notes: z.string().optional(),
    technique: facetList('technique'),
    subject: facetList('subject'),
    lineage: facetList('lineage'),
    sources: z.array(source).default([]),
    added: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'added must be a date like 2026-09-27'),
    /** Who made a human-made piece; a piece a model made has `model` instead. */
    author: z.string().trim().min(1).optional(),
    /** The model id that made the piece, credited by its name under `models:` in taxonomy.yaml. */
    model: z.string().trim().min(1).optional(),
    license: z.string().optional(),
    franchise: z
      .object({ title: z.string().min(1), owner: z.string().min(1) })
      .strict()
      .optional(),
    draft: z.boolean().default(false),
    proposed_facets: z.record(z.string(), z.array(z.string())).default({}),
    variants: variantsMeta.optional(),

    // Attached by the loader, not read from meta.yaml.
    slug: z.string(),
    /** The folder's license: `license`, FAN_WORK with a `franchise`, or DEFAULT_LICENSE for a piece a model made without a recreation source. */
    resolvedLicense: z.string(),
    /** Whether design.py exists; legacy pieces (source.svg + palette.yaml) have no script. */
    hasScript: z.boolean(),
    hasData: z.boolean(),
    /** design.py text, null for legacy pieces. */
    script: z.string().nullable(),
    /** Aspects the piece composes natively, in SITE_ASPECTS order; the rest are crops of 16:9. */
    aspects: z.array(z.string()).min(1),
    /** The default version's build, which the index and the social card show. */
    ...build,
    /**
     * The versions a visitor can switch between, the default first and then the named variants in
     * meta.yaml order, draft ones only in `astro dev`; [] when no named variant is shown.
     */
    versions: z.array(version),
    /** Page views on walldye.com, all of them. */
    views: z.number().int().nonnegative(),
    /** Page views weighted by age, a day's halving every HALF_LIFE_DAYS (src/server/views.ts); rounded to 0.01. */
    recent: z.number().nonnegative(),
    /** Place on featured.yaml, from 0; absent when the piece is not on it. */
    featured: z.number().int().nonnegative().optional(),
  })
  .strict()
  .superRefine((m, ctx) => {
    const issue = (message: string, path: string[] = []) =>
      ctx.addIssue({ code: 'custom', message, path });
    if (!SLUG.test(m.slug))
      issue(`folder name ${m.slug} must be lowercase words joined by single hyphens`, ['slug']);
    if (reservedSlug(m.slug)) issue(`slug ${m.slug} is reserved for a site route`, ['slug']);
    if (!m.author && !m.model)
      issue('needs model: (the model id that made it) or author: (who did)', ['model']);
    else if (m.model && !TAXONOMY.models[m.model])
      issue(`model ${m.model} needs a credit name under models: in taxonomy.yaml`, ['model']);
    if (
      m.license &&
      m.license !== DEFAULT_LICENSE &&
      m.license !== FAN_WORK &&
      !LICENSE_LINES[m.license]
    ) {
      issue(`license ${m.license} needs a plain-words line in LICENSE_LINES (src/lib/labels.ts)`, [
        'license',
      ]);
    }
  });
