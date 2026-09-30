import { getCollection } from 'astro:content';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import type { APIRoute, GetStaticPaths } from 'astro';

const TYPES = { svg: 'image/svg+xml', 'slots.json': 'application/json' } as const;

/**
 * Every template and slots.json of every version, byte for byte, at /t/<hash>.svg and
 * /t/<hash>.slots.json (servedUrl); identical files share one URL.
 */
export const getStaticPaths = (async () => {
  const files = new Map<string, { path: string; type: string }>();
  for (const { data } of await getCollection('wallpapers')) {
    for (const b of [data, ...data.versions]) {
      for (const t of Object.values(b.templates))
        files.set(`${t.hash}.svg`, { path: t.path, type: TYPES.svg });
      files.set(`${b.slotsHash}.slots.json`, { path: b.slotsPath, type: TYPES['slots.json'] });
    }
  }
  return [...files].map(([file, props]) => ({ params: { file }, props }));
}) satisfies GetStaticPaths;

export const GET: APIRoute = async ({ props }) =>
  new Response(await readFile(resolve(props.path as string)), {
    headers: { 'Content-Type': props.type as string },
  });
