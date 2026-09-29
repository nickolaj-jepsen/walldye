import { getCollection } from 'astro:content';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import type { APIRoute, GetStaticPaths } from 'astro';

/** Every version's slots.json, byte for byte, at /t/<sha256[:12]>.slots.json; identical files share one URL. */
export const getStaticPaths = (async () => {
  const files = new Map<string, string>();
  for (const { data } of await getCollection('wallpapers')) {
    for (const b of [data, ...data.versions])
      files.set(b.slotsUrl.slice(3, -'.slots.json'.length), b.slotsPath);
  }
  return [...files].map(([hash, path]) => ({ params: { hash }, props: { path } }));
}) satisfies GetStaticPaths;

export const GET: APIRoute = async ({ props }) =>
  new Response(await readFile(resolve(props.path as string)), {
    headers: { 'Content-Type': 'application/json' },
  });
