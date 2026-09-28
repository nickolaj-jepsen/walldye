import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import type { APIRoute, GetStaticPaths } from 'astro';
import { getCollection } from 'astro:content';

/** Every drawable piece's data/ files, byte for byte, at /t/<sha256[:12]>.data; identical files share one URL. */
export const getStaticPaths = (async () => {
  const files = new Map<string, string>();
  for (const { data } of await getCollection('wallpapers')) for (const f of data.dataFiles) files.set(f.url.slice(3, -'.data'.length), f.path);
  return [...files].map(([hash, path]) => ({ params: { hash }, props: { path } }));
}) satisfies GetStaticPaths;

export const GET: APIRoute = async ({ props }) =>
  new Response(await readFile(resolve(props.path as string)), { headers: { 'Content-Type': 'application/octet-stream' } });
