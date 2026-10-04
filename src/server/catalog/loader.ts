/** The Astro loader of the wallpapers collection. */
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import type { Loader, LoaderContext } from 'astro/loaders';
import { typesetMeta, typesetNotes } from '../../lib/typeset';
import { isDraft } from '../meta';
import { parseYaml } from '../yaml';
import { attach } from './build';
import { loadFeatured, loadStats, ROOT, rootPath, WALLPAPERS } from './files';

/**
 * Loads wallpapers/<slug>/meta.yaml (the folder name is the id) with build/slots.json, the
 * templates and their content-hashed URLs, the same for each named variant, design.py, the
 * resolved license, the page views and downloads in stats/ and the place on featured.yaml. Draft pieces and draft variants load only in
 * `astro dev` or with WALLDYE_DRAFTS=1; notes Markdown is rendered into the entry (`render(entry)`), and the other visible
 * text gets typographer's quotes.
 */
export function wallpapers(): Loader {
  return {
    name: 'walldye-wallpapers',
    async load(context: LoaderContext) {
      const { store, parseData, generateDigest, renderMarkdown, watcher, logger } = context;
      // Only the PR preview sets WALLDYE_DRAFTS; the dist e2e tests and production serves never does.
      const dev = import.meta.env.DEV || process.env.WALLDYE_DRAFTS === '1';

      const sync = async () => {
        const seen = new Set<string>();
        const stats = loadStats();
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
          const v = stats.get(slug);
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
        watcher.add(WALLPAPERS);
        let timer: ReturnType<typeof setTimeout> | undefined;
        const onChange = (path: string) => {
          const at = resolve(path);
          if (!at.startsWith(WALLPAPERS)) return;
          clearTimeout(timer);
          // `walldye build` writes a dozen files in a burst; resync once it settles.
          timer = setTimeout(() => sync().catch((e: Error) => logger.error(e.message)), 150);
        };
        for (const event of ['add', 'change', 'unlink'] as const) watcher.on(event, onChange);
      }
    },
  };
}
