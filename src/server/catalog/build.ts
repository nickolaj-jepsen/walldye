/** Reading a piece's build output: the templates and slots.json each version's build/ holds. */
import { createHash } from 'node:crypto';
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import type { z } from 'astro/zod';
import { DEFAULT_VARIANT, SITE_ASPECTS } from '../../lib/content';
import { servedHash, servedUrl } from '../../lib/recolor';
import { licenseOf, namedVariants, variantsMeta } from '../meta';
import { rootPath, WALLPAPERS } from './files';
import type { template, version } from './schema';

type SlotsEntry = { file: string; sha256: string; n: number };

const sha256 = (data: Buffer | string) => createHash('sha256').update(data).digest('hex');

/** The templates, slots.json and focus of one build directory; throws naming the file when it is stale. */
export function readBuild(slug: string, dir: string) {
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
      const sha = sha256(readFileSync(file));
      if (sha !== entry.sha256)
        throw new Error(`${rootPath(file)} differs from slots.json: ${run}`);
      const hash = servedHash(sha);
      templates[key] = {
        file: entry.file,
        path: rootPath(file),
        hash,
        url: servedUrl(hash, 'svg'),
      };
    }
  }
  if (!templates['16:9/dark'])
    throw new Error(`${rootPath(slotsPath)} has no 16:9/dark template: ${run}`);
  const slotsHash = servedHash(sha256(slotsBytes));
  return {
    templates,
    slotsHash,
    slotsUrl: servedUrl(slotsHash, 'slots.json'),
    slotsPath: rootPath(slotsPath),
    focus: (Array.isArray(slots.focus) ? slots.focus : [0.5, 0.5]) as [number, number],
  };
}

/**
 * The attached fields for one folder, read from build/, each shown variant's build/<variant>/ and
 * design.py. Draft variants are read only in `dev`, where one that is not built yet is skipped with
 * a warning; anything else stale throws naming the file.
 */
export function attach(
  slug: string,
  meta: Record<string, unknown>,
  dev: boolean,
  warn: (message: string) => void,
  wallpapers: string = WALLPAPERS,
) {
  const dir = join(wallpapers, slug);
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
