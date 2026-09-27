import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import type { APIRoute, GetStaticPaths } from 'astro';
import { getCollection } from 'astro:content';

/** Each piece's build/slots.json, byte for byte, at /t/<sha256[:12]>.slots.json. */
export const getStaticPaths = (async () =>
  (await getCollection('wallpapers')).map(({ data }) => ({
    params: { hash: data.slotsUrl.slice(3, -'.slots.json'.length) },
    props: { path: `wallpapers/${data.slug}/build/slots.json` },
  }))) satisfies GetStaticPaths;

export const GET: APIRoute = async ({ props }) =>
  new Response(await readFile(resolve(props.path as string)), { headers: { 'Content-Type': 'application/json' } });
