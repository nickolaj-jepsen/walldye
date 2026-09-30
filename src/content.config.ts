import { defineCollection } from 'astro:content';
import { createHash } from 'node:crypto';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join, relative, resolve, sep } from 'node:path';
import type { Loader, LoaderContext } from 'astro/loaders';
import { z } from 'astro/zod';
import { DEFAULT_VARIANT, SITE_ASPECTS } from './lib/content';
import { LICENSE_LINES, type TaxonomyFacet } from './lib/labels';
import {
  DEFAULT_LICENSE,
  FAN_WORK,
  isDraft,
  licenseOf,
  namedVariants,
  reservedSlug,
  typesetMeta,
  variantsMeta,
} from './lib/meta';
import { DAY_FILE, type Day, parseDay, renames, type Views, viewTotals } from './lib/views';
import { TAXONOMY } from './server/taxonomy';
import { parseYaml } from './server/yaml';

// Astro runs from the project root (as Base.astro assumes); this module is bundled, so import.meta.url is no anchor.
const ROOT = resolve('.');
const WALLPAPERS = join(ROOT, 'wallpapers');
/** The `stats` branch's day files, checked out by CI; absent locally unless fetched. */
const VIEWS = join(ROOT, 'stats', 'views');
/** The index's featured pieces, in order. */
const FEATURED = join(ROOT, 'featured.yaml');

/** `path` relative to the project root, with forward slashes; the endpoints read files by it. */
const rootPath = (path: string) => relative(ROOT, path).split(sep).join('/');

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
 * One wallpaper: meta.yaml in the shape the pages read, plus what the loader attaches from the
 * folder. walldye check owns the rest of the meta.yaml rules; this keeps only what a page needs to
 * render: facet values, credit and license words the site has, and a slug that is a free route.
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
    /** Page views weighted by age, a day's halving every HALF_LIFE_DAYS (src/lib/views.ts); rounded to 0.01. */
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
      if (hash !== entry.sha256)
        throw new Error(`${rootPath(file)} differs from slots.json: ${run}`);
      templates[key] = {
        file: entry.file,
        path: rootPath(file),
        url: `/t/${hash.slice(0, 12)}.svg`,
      };
    }
  }
  if (!templates['16:9/dark'])
    throw new Error(`${rootPath(slotsPath)} has no 16:9/dark template: ${run}`);
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
function attach(
  slug: string,
  meta: Record<string, unknown>,
  dev: boolean,
  warn: (message: string) => void,
) {
  const dir = join(WALLPAPERS, slug);
  const main = readBuild(slug, join(dir, 'build'));
  const aspects = SITE_ASPECTS.filter((a) => main.templates[`${a}/dark`]);
  const unlit = aspects.find((a) => !main.templates[`${a}/light`]);
  if (unlit)
    throw new Error(`${main.slotsPath} has no ${unlit}/light template: run walldye build ${slug}`);

  const description = typeof meta.description === 'string' ? meta.description.trim() : '';
  const versions: z.infer<typeof version>[] = [];
  // A malformed variants: is the schema's to report; the versions would only repeat it.
  if (variantsMeta.safeParse(meta.variants).success) {
    const keys = Object.keys(main.templates).sort().join(', ');
    for (const v of namedVariants(meta)) {
      if (v.draft && !dev) continue;
      let named: ReturnType<typeof readBuild>;
      try {
        named = readBuild(slug, join(dir, 'build', v.name));
        const got = Object.keys(named.templates).sort().join(', ');
        if (got !== keys)
          throw new Error(
            `${named.slotsPath} has templates for ${got}, not ${keys} like build/slots.json: run walldye build ${slug}`,
          );
      } catch (e) {
        if (!v.draft) throw e;
        warn(`skipping draft variant ${slug} ${v.name}: ${(e as Error).message}`);
        continue;
      }
      const own = typeof v.description === 'string' ? v.description.trim() : '';
      versions.push({
        name: v.name,
        label: String(v.label).trim(),
        description: own || description,
        draft: v.draft,
        ...named,
      });
    }
    if (versions.length) {
      const { label } = (meta.variants as Record<string, { label: string }>)[DEFAULT_VARIANT];
      versions.unshift({
        name: DEFAULT_VARIANT,
        label: label.trim(),
        description,
        draft: false,
        ...main,
      });
    }
  }

  const scriptPath = join(dir, 'design.py');
  const hasScript = existsSync(scriptPath);
  const license = licenseOf(meta);
  return {
    slug,
    resolvedLicense: typeof license === 'string' ? license : '',
    hasScript,
    hasData: existsSync(join(dir, 'data')),
    script: hasScript ? readFileSync(scriptPath, 'utf8') : null,
    aspects,
    ...main,
    versions,
  };
}

/**
 * Place by slug on featured.yaml, from 0; empty without the file. Throws when it is not a list of
 * slugs, names one twice, or names a folder that is not among `slugs`.
 */
function loadFeatured(slugs: readonly string[]): Map<string, number> {
  if (!existsSync(FEATURED)) return new Map();
  const list: unknown = parseYaml(readFileSync(FEATURED, 'utf8')) ?? [];
  if (!Array.isArray(list) || !list.every((s) => typeof s === 'string'))
    throw new Error('featured.yaml: must be a list of slugs');
  const out = new Map<string, number>();
  for (const [i, slug] of list.entries()) {
    if (out.has(slug)) throw new Error(`featured.yaml: ${slug} is listed twice`);
    if (!slugs.includes(slug))
      throw new Error(`featured.yaml: ${slug} is not a folder in wallpapers/`);
    out.set(slug, i);
  }
  return out;
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
  return viewTotals(
    days,
    existsSync(redirects) ? renames(readFileSync(redirects, 'utf8')) : new Map(),
  );
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
        .replace(
          /\b(?:(?=[A-Za-z]*\d)(?=\d*[A-Za-z])[A-Za-z\d]+|\d+\.\d+|\d+ ?× ?\d+)\b/g,
          '<span class="lnum">$&</span>',
        );
    })
    .join('');
}

/**
 * Loads wallpapers/<slug>/meta.yaml (the folder name is the id) with build/slots.json, the
 * templates and their content-hashed URLs, the same for each named variant, design.py, the
 * resolved license, the page views in stats/views/ and the place on featured.yaml. Draft pieces and draft variants load only in
 * `astro dev` or with WALLDYE_DRAFTS=1; notes Markdown is rendered into the entry (`render(entry)`), and the other visible
 * text gets typographer's quotes.
 */
function wallpapers(): Loader {
  return {
    name: 'walldye-wallpapers',
    async load(context: LoaderContext) {
      const { store, parseData, generateDigest, renderMarkdown, watcher, logger } = context;
      // Only the PR preview sets WALLDYE_DRAFTS; the dist e2e tests and production serves never does.
      const dev = import.meta.env.DEV || process.env.WALLDYE_DRAFTS === '1';

      const sync = async () => {
        const seen = new Set<string>();
        const views = loadViews();
        const slugs = readdirSync(WALLPAPERS, { withFileTypes: true })
          .filter((d) => d.isDirectory() && existsSync(join(WALLPAPERS, d.name, 'meta.yaml')))
          .map((d) => d.name)
          .sort();
        const featured = loadFeatured(slugs);
        for (const slug of slugs) {
          const filePath = rootPath(join(WALLPAPERS, slug, 'meta.yaml'));
          let meta: Record<string, unknown>;
          try {
            meta = (parseYaml(readFileSync(join(ROOT, filePath), 'utf8')) ?? {}) as Record<
              string,
              unknown
            >;
          } catch (e) {
            throw new Error(`${filePath}: not valid YAML: ${(e as Error).message}`);
          }
          if (typeof meta !== 'object' || Array.isArray(meta))
            throw new Error(`${filePath}: must be a mapping`);
          // meta.yaml keeps typewriter quotes; the notes get the same curling from Markdown.
          meta = typesetMeta(meta);
          if (isDraft(meta) && !dev) continue;
          let attached: ReturnType<typeof attach>;
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
          const rank = featured.get(slug);
          const data = await parseData<Record<string, unknown>>({
            id: slug,
            data: {
              ...meta,
              ...attached,
              ...counts,
              ...(rank === undefined ? {} : { featured: rank }),
            },
            filePath,
          });
          const notes =
            typeof data.notes === 'string' && data.notes.trim() ? data.notes : undefined;
          const rendered = notes ? await renderMarkdown(notes) : undefined;
          if (rendered) rendered.html = typesetNotes(rendered.html);
          seen.add(slug);
          store.set({
            id: slug,
            data,
            filePath,
            digest: generateDigest({ data, notes: rendered?.html ?? '' }),
            rendered,
          });
        }
        for (const id of store.keys()) if (!seen.has(id)) store.delete(id);
      };

      await sync();

      if (watcher) {
        watcher.add([WALLPAPERS, FEATURED]);
        let timer: ReturnType<typeof setTimeout> | undefined;
        const onChange = (path: string) => {
          const at = resolve(path);
          if (!at.startsWith(WALLPAPERS) && at !== FEATURED) return;
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
