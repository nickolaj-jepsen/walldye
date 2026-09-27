import { createHash } from 'node:crypto';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { defineCollection } from 'astro:content';
import type { Loader, LoaderContext } from 'astro/loaders';
import { z } from 'astro/zod';
import YAML from 'yaml';
import { SITE_ASPECTS } from './lib/content';
import { DEFAULT_LICENSE, FAN_WORK, isDraft, licenseOf } from './lib/meta';
import {
  FACET_LABELS,
  LICENCE_LINES,
  TAKEDOWN_CONTACT,
  TAXONOMY_FACETS,
  UNLISTED,
  type TaxonomyFacet,
} from './lib/labels';

// Astro runs from the project root (as Base.astro assumes); this module is bundled, so import.meta.url is no anchor.
const ROOT = resolve('.');
const WALLPAPERS = join(ROOT, 'wallpapers');

/** Slugs that would shadow a site route or file (walldye/tools/lint.py reserved()). */
const RESERVED = new Set(['about', 'index', 't', 'og', 'fonts', '404', 'robots', 'favicon']);
const SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

/** Whether a slug collides with a site route or file: RESERVED, `sitemap*` or `_*`. */
export function reservedSlug(slug: string): boolean {
  return RESERVED.has(slug) || slug.startsWith('sitemap') || slug.startsWith('_');
}

function loadTaxonomy(): Record<TaxonomyFacet, string[]> {
  const data = (YAML.parse(readFileSync(join(ROOT, 'taxonomy.yaml'), 'utf8')) ?? {}) as Record<string, unknown>;
  const out = {} as Record<TaxonomyFacet, string[]>;
  for (const facet of TAXONOMY_FACETS) {
    const values = data[facet] ?? [];
    if (!Array.isArray(values) || !values.every((v) => typeof v === 'string')) throw new Error(`taxonomy.yaml: ${facet} must be a list of slugs`);
    out[facet] = values;
  }
  return out;
}

const taxonomy = loadTaxonomy();
const facetList = (facet: TaxonomyFacet) =>
  z
    .array(z.string())
    .default([])
    .superRefine((vs, ctx) => {
      for (const v of vs) {
        if (!taxonomy[facet].includes(v)) ctx.addIssue({ code: 'custom', message: `${v} is not in taxonomy.yaml (suggest it under proposed_facets)` });
      }
    });

const source = z
  .object({
    kind: z.enum(['recreation', 'inspiration', 'reference', 'data']),
    title: z.string().min(1).optional(),
    author: z.string().min(1).optional(),
    year: z.union([z.number().int(), z.string().min(1)]).optional(),
    url: z.url().optional(),
    /** BCP 47 language of a foreign title, set on its `<i lang>`. */
    lang: z.string().min(2).optional(),
  })
  .strict()
  .refine((s) => s.title || s.author, { message: 'a source needs a title or an author' });

const template = z.object({
  /** File name inside build/. */
  file: z.string(),
  /** Repo-relative path of the file. */
  path: z.string(),
  /** Served copy: /t/<sha256[:12]>.svg. */
  url: z.string(),
});

/**
 * One wallpaper: meta.yaml (docs/design.md, Metadata) validated against taxonomy.yaml, the
 * licence rules and the reserved slugs, plus what the loader attaches from the folder.
 */
const wallpaper = z
  .object({
    title: z.string().trim().min(1),
    description: z.string().trim().min(1),
    notes: z.string().optional(),
    technique: facetList('technique'),
    subject: facetList('subject'),
    lineage: facetList('lineage'),
    sources: z.array(source).default([]),
    added: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'added must be a date like 2026-09-27'),
    themes: z
      .union([z.tuple([z.literal('dark'), z.literal('light')]), z.tuple([z.literal('dark')])])
      .default(['dark', 'light']),
    author: z.string().trim().min(1),
    ai_generated: z.boolean().default(false),
    model: z.string().optional(),
    license: z.string().optional(),
    franchise: z.object({ title: z.string().min(1), owner: z.string().min(1) }).strict().optional(),
    draft: z.boolean().default(false),
    proposed_facets: z.record(z.string(), z.array(z.string())).default({}),

    // Attached by the loader, not read from meta.yaml.
    slug: z.string(),
    /** The folder's licence: `license`, or DEFAULT_LICENSE for an AI-generated piece without a recreation source. */
    licence: z.string(),
    /** Whether design.py exists; legacy pieces (source.svg + palette.yaml) have no script. */
    hasScript: z.boolean(),
    /** design.py text, null for legacy pieces. */
    script: z.string().nullable(),
    /** Aspects the piece composes natively, in SITE_ASPECTS order; the rest are crops of 16:9. */
    aspects: z.array(z.string()).min(1),
    /** Templates by slots.json key, `<aspect>/<regime>`. */
    templates: z.record(z.string(), template),
    /** Served copy of build/slots.json: /t/<sha256[:12]>.slots.json. */
    slotsUrl: z.string(),
    /** Ink-weighted centroid of the 16:9 template, each 0..1. */
    focus: z.tuple([z.number(), z.number()]),
  })
  .strict()
  .superRefine((m, ctx) => {
    const issue = (message: string, path: string[] = []) => ctx.addIssue({ code: 'custom', message, path });
    if (!SLUG.test(m.slug)) issue(`folder name ${m.slug} must be lowercase words joined by single hyphens`, ['slug']);
    if (reservedSlug(m.slug)) issue(`slug ${m.slug} is reserved for a site route`, ['slug']);
    const recreation = m.sources.some((s) => s.kind === 'recreation');
    if (!m.license && recreation) issue('a kind: recreation source needs an explicit license: (ask the owner)', ['license']);
    else if (!m.license && !m.ai_generated) issue('human-made pieces need an explicit license:', ['license']);
    if (m.licence && !existsSync(join(ROOT, 'LICENSES', `${m.licence}.txt`))) issue(`license ${m.licence} has no LICENSES/${m.licence}.txt`, ['license']);
    if (m.license === FAN_WORK) {
      if (!m.franchise) issue(`license ${FAN_WORK} needs franchise: {title, owner}`, ['franchise']);
      if (!TAKEDOWN_CONTACT) issue('fan-work pieces need TAKEDOWN_CONTACT in src/lib/labels.ts', ['license']);
    } else if (m.licence && m.licence !== DEFAULT_LICENSE && !LICENCE_LINES[m.licence]) {
      issue(`license ${m.licence} needs a plain-words line in LICENCE_LINES (src/lib/labels.ts)`, ['license']);
    }
    if (m.model && !m.ai_generated) issue('model: is only for ai_generated pieces', ['model']);
    if (Object.values(m.proposed_facets).some((vs) => vs.length) && !m.draft) issue('proposed_facets are only allowed while draft: true', ['proposed_facets']);
    for (const facet of TAXONOMY_FACETS) {
      for (const v of m[facet]) {
        if (taxonomy[facet].includes(v) && !UNLISTED[facet].includes(v) && !FACET_LABELS[facet][v]) issue(`${v} needs a label in src/lib/labels.ts`, [facet]);
      }
    }
  });

type SlotsEntry = { file: string; sha256: string; n: number };

const sha256 = (data: Buffer | string) => createHash('sha256').update(data).digest('hex');

/** The attached fields for one folder, read from build/ and design.py; throws naming the file when build/ is stale. */
function attach(slug: string, meta: Record<string, unknown>) {
  const dir = join(WALLPAPERS, slug);
  const rel = (...parts: string[]) => ['wallpapers', slug, ...parts].join('/');
  const slotsPath = join(dir, 'build', 'slots.json');
  if (!existsSync(slotsPath)) throw new Error(`${rel('build', 'slots.json')} is missing: run walldye build ${slug}`);
  const slotsBytes = readFileSync(slotsPath);
  const slots = JSON.parse(slotsBytes.toString('utf8')) as Record<string, unknown>;

  const templates: Record<string, z.infer<typeof template>> = {};
  const aspects: string[] = [];
  for (const aspect of SITE_ASPECTS) {
    for (const regime of ['dark', 'light'] as const) {
      const key = `${aspect}/${regime}`;
      const entry = slots[key] as SlotsEntry | undefined;
      if (!entry) continue;
      const file = join(dir, 'build', entry.file);
      if (!existsSync(file)) throw new Error(`${rel('build', entry.file)} is missing: run walldye build ${slug}`);
      const hash = sha256(readFileSync(file));
      if (hash !== entry.sha256) throw new Error(`${rel('build', entry.file)} differs from slots.json: run walldye build ${slug}`);
      templates[key] = { file: entry.file, path: rel('build', entry.file), url: `/t/${hash.slice(0, 12)}.svg` };
      if (regime === 'dark') aspects.push(aspect);
    }
  }
  if (!templates['16:9/dark']) throw new Error(`${rel('build', 'slots.json')} has no 16:9/dark template: run walldye build ${slug}`);
  const light = Array.isArray(meta.themes) ? meta.themes.includes('light') : true;
  for (const aspect of aspects) {
    if (light !== Boolean(templates[`${aspect}/light`])) {
      throw new Error(`${rel('build', 'slots.json')} does not match themes in meta.yaml: run walldye build ${slug}`);
    }
  }

  const scriptPath = join(dir, 'design.py');
  const hasScript = existsSync(scriptPath);
  const licence = licenseOf(meta);
  const focus = Array.isArray(slots.focus) ? slots.focus : [0.5, 0.5];
  return {
    slug,
    licence: typeof licence === 'string' ? licence : '',
    hasScript,
    script: hasScript ? readFileSync(scriptPath, 'utf8') : null,
    aspects,
    templates,
    slotsUrl: `/t/${sha256(slotsBytes).slice(0, 12)}.slots.json`,
    focus,
  };
}

/** Notes HTML with `<em>` as `<i>` (italics mark titles), acronyms in `<abbr>` and letter-like figures (Z64, 5.5) in `.lnum`; tags, entities and code are left alone. */
function typesetNotes(html: string): string {
  const skip = /^<(\/?)(code|pre|abbr|kbd|samp)\b/i;
  let depth = 0;
  return html
    .replace(/<(\/?)em>/g, '<$1i>')
    .split(/(<[^>]+>|&#?\w+;)/)
    .map((part) => {
      if (part.startsWith('&')) return part;
      if (part.startsWith('<')) {
        const m = skip.exec(part);
        if (m) depth += m[1] ? -1 : 1;
        return part;
      }
      if (depth > 0) return part;
      return part
        .replace(/\b[A-Z]{2,}\b/g, '<abbr>$&</abbr>')
        .replace(/\b(?:(?=[A-Za-z]*\d)(?=\d*[A-Za-z])[A-Za-z\d]+|\d+\.\d+|\d+ ?× ?\d+)\b/g, '<span class="lnum">$&</span>');
    })
    .join('');
}

/**
 * Loads wallpapers/<slug>/meta.yaml (the folder name is the id) with build/slots.json, the
 * templates and their content-hashed URLs, design.py and the resolved licence. Drafts load only
 * in `astro dev`; notes Markdown is rendered into the entry (`render(entry)`).
 */
function wallpapers(): Loader {
  return {
    name: 'walldye-wallpapers',
    async load(context: LoaderContext) {
      const { store, parseData, generateDigest, renderMarkdown, watcher, logger } = context;
      const dev = import.meta.env.DEV;

      const sync = async () => {
        const seen = new Set<string>();
        const slugs = readdirSync(WALLPAPERS, { withFileTypes: true })
          .filter((d) => d.isDirectory() && existsSync(join(WALLPAPERS, d.name, 'meta.yaml')))
          .map((d) => d.name)
          .sort();
        for (const slug of slugs) {
          const filePath = `wallpapers/${slug}/meta.yaml`;
          let meta: Record<string, unknown>;
          try {
            meta = (YAML.parse(readFileSync(join(ROOT, filePath), 'utf8')) ?? {}) as Record<string, unknown>;
          } catch (e) {
            throw new Error(`${filePath}: not valid YAML: ${(e as Error).message}`);
          }
          if (typeof meta !== 'object' || Array.isArray(meta)) throw new Error(`${filePath}: must be a mapping`);
          if (isDraft(meta) && !dev) continue;
          let attached;
          try {
            attached = attach(slug, meta);
          } catch (e) {
            // A draft mid-build must not take the dev server down.
            if (isDraft(meta)) {
              logger.warn(`skipping draft ${slug}: ${(e as Error).message}`);
              continue;
            }
            throw e;
          }
          const data = await parseData<Record<string, unknown>>({ id: slug, data: { ...meta, ...attached }, filePath });
          const notes = typeof data.notes === 'string' && data.notes.trim() ? data.notes : undefined;
          const rendered = notes ? await renderMarkdown(notes) : undefined;
          if (rendered) rendered.html = typesetNotes(rendered.html);
          seen.add(slug);
          store.set({ id: slug, data, filePath, digest: generateDigest({ data, notes: rendered?.html ?? '' }), rendered });
        }
        for (const id of store.keys()) if (!seen.has(id)) store.delete(id);
      };

      await sync();

      if (watcher) {
        watcher.add(WALLPAPERS);
        let timer: ReturnType<typeof setTimeout> | undefined;
        const onChange = (path: string) => {
          if (!resolve(path).startsWith(WALLPAPERS)) return;
          clearTimeout(timer);
          // `walldye build` writes a dozen files in a burst; resync once it settles.
          timer = setTimeout(() => sync().catch((e: Error) => logger.error(e.message)), 150);
        };
        for (const event of ['add', 'change', 'unlink'] as const) watcher.on(event, onChange);
      }
    },
  };
}

export const collections = {
  wallpapers: defineCollection({ loader: wallpapers(), schema: wallpaper }),
};
