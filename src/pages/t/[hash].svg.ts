import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import type { APIRoute, GetStaticPaths } from 'astro';
import { getCollection } from 'astro:content';

/** Every template of every version, byte for byte, at /t/<sha256[:12]>.svg; identical templates share one URL. */
export const getStaticPaths = (async () => {
  const files = new Map<string, string>();
  for (const { data } of await getCollection('wallpapers')) {
    for (const b of [data, ...data.versions]) for (const t of Object.values(b.templates)) files.set(t.url.slice(3, -4), t.path);
  }
  return [...files].map(([hash, path]) => ({ params: { hash }, props: { path } }));
}) satisfies GetStaticPaths;

export const GET: APIRoute = async ({ props }) =>
  new Response(await readFile(resolve(props.path as string)), { headers: { 'Content-Type': 'image/svg+xml' } });
