import { createHash } from 'node:crypto';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join, relative, resolve, sep } from 'node:path';
import { defineCollection } from 'astro:content';
import type { Loader, LoaderContext } from 'astro/loaders';
import { z } from 'astro/zod';
import YAML from 'yaml';
import { DEFAULT_VARIANT, SITE_ASPECTS } from './lib/content';
import { DEFAULT_LICENSE, FAN_WORK, isDraft, licenseOf, namedVariants, typesetMeta, variantsMeta } from './lib/meta';
import { FACET_LABELS, LICENCE_LINES, MODEL_NAMES, TAXONOMY_FACETS, type TaxonomyFacet } from './lib/labels';
import { DAY_FILE, parseDay, renames, viewTotals, type Day, type Views } from './lib/views';

// Astro runs from the project root (as Base.astro assumes); this module is bundled, so import.meta.url is no anchor.
const ROOT = resolve('.');
const WALLPAPERS = join(ROOT, 'wallpapers');
/** The `stats` branch's day files, checked out by CI; absent locally unless fetched. */
const VIEWS = join(ROOT, 'stats', 'views');

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
  .refine((s) => !(s.title && s.topic), { message: 'a title names a work and a topic anything else; not both' })
  .refine((s) => s.title || s.topic || s.author, { message: 'a source needs a title, a topic or an author' });

const template = z.object({
  /** File name inside its build directory. */
  file: z.string(),
  /** Path of the file from the project root. */
  path: z.string(),
  /** Served copy: /t/<sha256[:12]>.svg. */
  url: z.string(),
});

const paramValue = z.union([z.number(), z.string(), z.boolean(), z.null()]);

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
  /** The version's params by field name, `seed` included. */
  params: z.record(z.string(), paramValue),
  /** Whether another seed draws this version differently. */
  redraw: z.boolean(),
};

/** A knob the detail page shows: the params schema from slots.json with meta.yaml's labels, in meta.yaml order. */
const knob = z
  .object({
    name: z.string(),
    label: z.string(),
    kind: z.enum(['int', 'float', 'bool', 'str']),
    lo: z.number().nullable(),
    hi: z.number().nullable(),
    /** Each value with its label; null for a range, a bool or text. */
    choices: z.array(z.object({ value: z.union([z.number(), z.string()]), label: z.string() })).nullable(),
    unit: z.string(),
    /** The longest text a text knob takes; null for any other knob. */
    maxLen: z.number().nullable(),
    /** The axis along which dragging the picture moves this knob, if any. */
    drag: z.enum(['x', 'y']).nullable(),
  })
  .strict();

/** meta.yaml `controls:`: false, or knob names mapped to a label or {label, choices, drag}. walldye check holds them to the design. */
const controlsMeta = z.union([
  z.literal(false),
  z.record(
    z.string(),
    z.union([
      z.string().trim().min(1),
      z
        .object({
          label: z.string().trim().min(1),
          choices: z.record(z.string(), z.string().trim().min(1)).optional(),
          drag: z.enum(['x', 'y']).optional(),
        })
        .strict(),
    ]),
  ),
]);

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
 * One wallpaper: meta.yaml validated against taxonomy.yaml, the
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
    /** Who made a human-made piece; a piece a model made has `model` instead. */
    author: z.string().trim().min(1).optional(),
    /** The model id that made the piece, credited by its MODEL_NAMES name. */
    model: z.string().trim().min(1).optional(),
    license: z.string().optional(),
    franchise: z.object({ title: z.string().min(1), owner: z.string().min(1) }).strict().optional(),
    draft: z.boolean().default(false),
    proposed_facets: z.record(z.string(), z.array(z.string())).default({}),
    variants: variantsMeta.optional(),
    controls: controlsMeta.optional(),

    // Attached by the loader, not read from meta.yaml.
    slug: z.string(),
    /** The folder's licence: `license`, FAN_WORK with a `franchise`, or DEFAULT_LICENSE for a piece a model made without a recreation source. */
    licence: z.string(),
    /** Whether design.py exists; legacy pieces (source.svg + palette.yaml) have no script. */
    hasScript: z.boolean(),
    hasData: z.boolean(),
    /** design.py text, null for legacy pieces. */
    script: z.string().nullable(),
    /** Aspects the piece composes natively, in SITE_ASPECTS order; the rest are crops of 16:9. */
    aspects: z.array(z.string()).min(1),
    /** The knobs the detail page shows; [] when meta.yaml labels none or turns the controls off. */
    knobs: z.array(knob),
    /** Whether the detail page may redraw the piece in the browser: it has a script and meta.yaml leaves the controls on. */
    drawable: z.boolean(),
    /** A drawable piece's data/ files, served at /t/<sha256[:12]>.data for the browser's draws. */
    dataFiles: z.array(z.object({ name: z.string(), path: z.string(), url: z.string() }).strict()),
    /** The default version's build, which the index and the social card show. */
    ...build,
    /**
     * The versions a visitor can switch between, the default first and then the named variants in
     * meta.yaml order, draft ones only in `astro dev`; [] when no named variant is shown.
     */
    versions: z.array(version),
    /** Page views on walldye.com, all of them. */
    views: z.number().int().nonnegative(),
    /** Page views weighted by age, a day's halving every HALF_LIFE_DAYS (src/lib/views.ts); rounded to 0.01. */
    recent: z.number().nonnegative(),
  })
  .strict()
  .superRefine((m, ctx) => {
    const issue = (message: string, path: string[] = []) => ctx.addIssue({ code: 'custom', message, path });
    if (!SLUG.test(m.slug)) issue(`folder name ${m.slug} must be lowercase words joined by single hyphens`, ['slug']);
    if (reservedSlug(m.slug)) issue(`slug ${m.slug} is reserved for a site route`, ['slug']);
    if (!m.author && !m.model) issue('needs model: (the model id that made it) or author: (who did)', ['model']);
    else if (m.author && m.model) issue('author: is for human-made pieces; a piece a model made has only model:', ['author']);
    else if (m.model && !MODEL_NAMES[m.model]) issue(`model ${m.model} needs a credit name in MODEL_NAMES (src/lib/labels.ts)`, ['model']);
    const recreation = m.sources.some((s) => s.kind === 'recreation');
    if (m.license && m.franchise) issue(`franchise: makes the piece fan work (${FAN_WORK}); drop license:`, ['license']);
    else if (m.license === FAN_WORK) issue('fan work is marked by franchise: {title, owner}, not license:', ['license']);
    else if (!m.license && !m.franchise && recreation) issue('a kind: recreation source needs an explicit license: (ask the owner)', ['license']);
    else if (!m.license && !m.franchise && !m.model) issue('human-made pieces need an explicit license:', ['license']);
    if (m.licence && !existsSync(join(ROOT, 'LICENSES', `${m.licence}.txt`))) issue(`license ${m.licence} has no LICENSES/${m.licence}.txt`, ['license']);
    if (m.licence && m.licence !== DEFAULT_LICENSE && m.licence !== FAN_WORK && !LICENCE_LINES[m.licence]) {
      issue(`license ${m.licence} needs a plain-words line in LICENCE_LINES (src/lib/labels.ts)`, ['license']);
    }
    if (m.hasData && !m.sources.some((s) => s.kind === 'data' || s.kind === 'recreation')) {
      issue('data/ needs a kind: data source (or the recreation it comes from)', ['sources']);
    }
    if (Object.values(m.proposed_facets).some((vs) => vs.length) && !m.draft) issue('proposed_facets are only allowed while draft: true', ['proposed_facets']);
    for (const facet of TAXONOMY_FACETS) {
      for (const v of m[facet]) {
        if (taxonomy[facet].includes(v) && !FACET_LABELS[facet][v]) issue(`${v} needs a label in src/lib/labels.ts`, [facet]);
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
    // A build from before these keys offers no controls until it is rebuilt.
    params: (isRecord(slots.params) ? slots.params : {}) as Record<string, z.infer<typeof paramValue>>,
    redraw: slots.redraw === true,
  };
}

const isRecord = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v);

type KnobSchema = {
  name: string;
  kind: string;
  lo: number | null;
  hi: number | null;
  choices: (number | string)[] | null;
  unit: string;
  max_len?: number | null;
};

/**
 * The knobs meta.yaml `controls:` labels, in its order, with their schema from the default version's
 * slots.json. [] when the controls are off or none are labelled; throws naming a knob the build does
 * not have (walldye check reports the rest of the rules).
 */
function shownKnobs(slug: string, controls: unknown, slotsPath: string): z.infer<typeof knob>[] {
  if (!isRecord(controls)) return [];
  const slots = JSON.parse(readFileSync(join(ROOT, slotsPath), 'utf8')) as Record<string, unknown>;
  const schema = new Map((Array.isArray(slots.knobs) ? (slots.knobs as KnobSchema[]) : []).map((k) => [k.name, k]));
  return Object.entries(controls).map(([name, entry]) => {
    const k = schema.get(name);
    if (!k) throw new Error(`${slotsPath} has no knob ${name} for controls: in meta.yaml: run walldye build ${slug}`);
    const { label, choices, drag } =
      typeof entry === 'string' ? { label: entry, choices: undefined, drag: undefined } : (entry as { label: string; choices?: Record<string, string>; drag?: 'x' | 'y' });
    return {
      name,
      label: label.trim(),
      kind: k.kind as z.infer<typeof knob>['kind'],
      lo: k.lo,
      hi: k.hi,
      choices: k.choices ? k.choices.map((value) => ({ value, label: (choices?.[String(value)] ?? String(value)).trim() })) : null,
      unit: k.unit,
      maxLen: k.max_len ?? null,
      drag: drag ?? null,
    };
  });
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
  const unlit = aspects.find((a) => !main.templates[`${a}/light`]);
  if (unlit) throw new Error(`${main.slotsPath} has no ${unlit}/light template: run walldye build ${slug}`);

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
  const drawable = hasScript && meta.controls !== false;
  const dataDir = join(dir, 'data');
  const dataFiles =
    drawable && existsSync(dataDir)
      ? readdirSync(dataDir)
          .sort()
          .map((name) => {
            const path = join(dataDir, name);
            return { name, path: rootPath(path), url: `/t/${sha256(readFileSync(path)).slice(0, 12)}.data` };
          })
      : [];
  return {
    slug,
    licence: typeof licence === 'string' ? licence : '',
    hasScript,
    hasData: existsSync(join(dir, 'data')),
    script: hasScript ? readFileSync(scriptPath, 'utf8') : null,
    aspects,
    knobs: drawable ? shownKnobs(slug, meta.controls, main.slotsPath) : [],
    drawable,
    dataFiles,
    ...main,
    versions,
  };
}

/** Views by slug from VIEWS, renames in public/_redirects folded in; empty without VIEWS. Throws naming a malformed file. */
function loadViews(): Map<string, Views> {
  if (!existsSync(VIEWS)) return new Map();
  const days = new Map<string, Day>();
  for (const file of readdirSync(VIEWS).sort()) {
    const date = DAY_FILE.exec(file)?.[1];
    if (!date) continue;
    try {
      days.set(date, parseDay(readFileSync(join(VIEWS, file), 'utf8')));
    } catch (e) {
      throw new Error(`${rootPath(join(VIEWS, file))}: ${(e as Error).message}`);
    }
  }
  const redirects = join(ROOT, 'public', '_redirects');
  return viewTotals(days, existsSync(redirects) ? renames(readFileSync(redirects, 'utf8')) : new Map());
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
 * templates and their content-hashed URLs, the same for each named variant, design.py, the
 * resolved licence and the page views in stats/views/. Draft pieces and draft variants load only in
 * `astro dev`; notes Markdown is rendered into the entry (`render(entry)`), and the other visible
 * text gets typographer's quotes.
 */
function wallpapers(): Loader {
  return {
    name: 'walldye-wallpapers',
    async load(context: LoaderContext) {
      const { store, parseData, generateDigest, renderMarkdown, watcher, logger } = context;
      const dev = import.meta.env.DEV;

      const sync = async () => {
        const seen = new Set<string>();
        const views = loadViews();
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
          const v = views.get(slug);
          const counts = { views: v?.views ?? 0, recent: Math.round((v?.recent ?? 0) * 100) / 100 };
          const data = await parseData<Record<string, unknown>>({ id: slug, data: { ...meta, ...attached, ...counts }, filePath });
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
