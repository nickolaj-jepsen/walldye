import { createHash } from 'node:crypto';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join, relative, resolve, sep } from 'node:path';
import { defineCollection } from 'astro:content';
import type { Loader, LoaderContext } from 'astro/loaders';
import { z } from 'astro/zod';
import YAML from 'yaml';
import { DEFAULT_VARIANT, SITE_ASPECTS } from './lib/content';
import { DEFAULT_LICENSE, FAN_WORK, isDraft, licenseOf, namedVariants, typesetMeta, variantsMeta } from './lib/meta';
import { FACET_LABELS, LICENCE_LINES, TAXONOMY_FACETS, UNLISTED, type TaxonomyFacet } from './lib/labels';

// Astro runs from the project root (as Base.astro assumes); this module is bundled, so import.meta.url is no anchor.
const ROOT = resolve('.');
// The e2e tests point WALLDYE_WALLPAPERS at a generated catalogue with named variants.
const WALLPAPERS = resolve(process.env.WALLDYE_WALLPAPERS || join(ROOT, 'wallpapers'));

/** `path` relative to the project root, with forward slashes; the endpoints read files by it. */
const rootPath = (path: string) => relative(ROOT, path).split(sep).join('/');

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
  /** File name inside its build directory. */
  file: z.string(),
  /** Path of the file from the project root. */
  path: z.string(),
  /** Served copy: /t/<sha256[:12]>.svg. */
  url: z.string(),
});

/** What the loader reads from one build directory: build/ for the default, build/<variant>/ for a named variant. */
const build = {
  /** Templates by slots.json key, `<aspect>/<regime>`. */
  templates: z.record(z.string(), template),
  /** Served copy of the slots.json: /t/<sha256[:12]>.slots.json. */
  slotsUrl: z.string(),
  /** Path of the slots.json from the project root. */
  slotsPath: z.string(),
  /** Ink-weighted centroid of the 16:9 template, each 0..1. */
  focus: z.tuple([z.number(), z.number()]),
};

/** One version of a piece: the default or a named variant, with its meta.yaml copy and its build. */
const version = z
  .object({
    /** `default` or the variant name. */
    name: z.string(),
    label: z.string(),
    /** The variant's own description, else the piece's. */
    description: z.string(),
    draft: z.boolean(),
    ...build,
  })
  .strict();

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
    variants: variantsMeta.optional(),

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
    /** The default version's build, which the index and the social card show. */
    ...build,
    /**
     * The versions a visitor can switch between, the default first and then the named variants in
     * meta.yaml order, draft ones only in `astro dev`; [] when no named variant is shown.
     */
    versions: z.array(version),
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

/** The templates, slots.json and focus of one build directory; throws naming the file when it is stale. */
function readBuild(slug: string, dir: string) {
  const run = `run walldye build ${slug}`;
  const slotsPath = join(dir, 'slots.json');
  if (!existsSync(slotsPath)) throw new Error(`${rootPath(slotsPath)} is missing: ${run}`);
  const slotsBytes = readFileSync(slotsPath);
  const slots = JSON.parse(slotsBytes.toString('utf8')) as Record<string, unknown>;
  const templates: Record<string, z.infer<typeof template>> = {};
  for (const aspect of SITE_ASPECTS) {
    for (const regime of ['dark', 'light'] as const) {
      const key = `${aspect}/${regime}`;
      const entry = slots[key] as SlotsEntry | undefined;
      if (!entry) continue;
      const file = join(dir, entry.file);
      if (!existsSync(file)) throw new Error(`${rootPath(file)} is missing: ${run}`);
      const hash = sha256(readFileSync(file));
      if (hash !== entry.sha256) throw new Error(`${rootPath(file)} differs from slots.json: ${run}`);
      templates[key] = { file: entry.file, path: rootPath(file), url: `/t/${hash.slice(0, 12)}.svg` };
    }
  }
  if (!templates['16:9/dark']) throw new Error(`${rootPath(slotsPath)} has no 16:9/dark template: ${run}`);
  return {
    templates,
    slotsUrl: `/t/${sha256(slotsBytes).slice(0, 12)}.slots.json`,
    slotsPath: rootPath(slotsPath),
    focus: (Array.isArray(slots.focus) ? slots.focus : [0.5, 0.5]) as [number, number],
  };
}

/**
 * The attached fields for one folder, read from build/, each shown variant's build/<variant>/ and
 * design.py. Draft variants are read only in `dev`, where one that is not built yet is skipped with
 * a warning; anything else stale throws naming the file.
 */
function attach(slug: string, meta: Record<string, unknown>, dev: boolean, warn: (message: string) => void) {
  const dir = join(WALLPAPERS, slug);
  const main = readBuild(slug, join(dir, 'build'));
  const aspects = SITE_ASPECTS.filter((a) => main.templates[`${a}/dark`]);
  const light = Array.isArray(meta.themes) ? meta.themes.includes('light') : true;
  if (aspects.some((a) => light !== Boolean(main.templates[`${a}/light`]))) {
    throw new Error(`${main.slotsPath} does not match themes in meta.yaml: run walldye build ${slug}`);
  }

  const description = typeof meta.description === 'string' ? meta.description.trim() : '';
  const versions: z.infer<typeof version>[] = [];
  // A malformed variants: is the schema's to report; the versions would only repeat it.
  if (variantsMeta.safeParse(meta.variants).success) {
    const keys = Object.keys(main.templates).sort().join(', ');
    for (const v of namedVariants(meta)) {
      if (v.draft && !dev) continue;
      let named;
      try {
        named = readBuild(slug, join(dir, 'build', v.name));
        const got = Object.keys(named.templates).sort().join(', ');
        if (got !== keys) throw new Error(`${named.slotsPath} has templates for ${got}, not ${keys} like build/slots.json: run walldye build ${slug}`);
      } catch (e) {
        if (!v.draft) throw e;
        warn(`skipping draft variant ${slug} ${v.name}: ${(e as Error).message}`);
        continue;
      }
      const own = typeof v.description === 'string' ? v.description.trim() : '';
      versions.push({ name: v.name, label: String(v.label).trim(), description: own || description, draft: v.draft, ...named });
    }
    if (versions.length) {
      const { label } = (meta.variants as Record<string, { label: string }>)[DEFAULT_VARIANT];
      versions.unshift({ name: DEFAULT_VARIANT, label: label.trim(), description, draft: false, ...main });
    }
  }

  const scriptPath = join(dir, 'design.py');
  const hasScript = existsSync(scriptPath);
  const licence = licenseOf(meta);
  return {
    slug,
    licence: typeof licence === 'string' ? licence : '',
    hasScript,
    script: hasScript ? readFileSync(scriptPath, 'utf8') : null,
    aspects,
    ...main,
    versions,
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
 * templates and their content-hashed URLs, the same for each named variant, design.py and the
 * resolved licence. Draft pieces and draft variants load only in `astro dev`; notes Markdown is
 * rendered into the entry (`render(entry)`), and the other visible text gets typographer's quotes.
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
          const filePath = rootPath(join(WALLPAPERS, slug, 'meta.yaml'));
          let meta: Record<string, unknown>;
          try {
            meta = (YAML.parse(readFileSync(join(ROOT, filePath), 'utf8')) ?? {}) as Record<string, unknown>;
          } catch (e) {
            throw new Error(`${filePath}: not valid YAML: ${(e as Error).message}`);
          }
          if (typeof meta !== 'object' || Array.isArray(meta)) throw new Error(`${filePath}: must be a mapping`);
          // meta.yaml keeps typewriter quotes; the notes get the same curling from Markdown.
          meta = typesetMeta(meta);
          if (isDraft(meta) && !dev) continue;
          let attached;
          try {
            attached = attach(slug, meta, dev, (message) => logger.warn(message));
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
