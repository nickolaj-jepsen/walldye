import { getCollection } from 'astro:content';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import type { APIRoute, GetStaticPaths } from 'astro';
import sharp from 'sharp';

const W = 1200;
const H = 630;

/** Social card: a 1200x630 band of the fireproof 16:9 template, centered on its focus where the band can move. */
export const getStaticPaths = (async () =>
  (await getCollection('wallpapers')).map(({ data }) => ({
    params: { slug: data.slug },
    props: { path: data.templates['16:9/dark'].path, focusY: data.focus[1] },
  }))) satisfies GetStaticPaths;

export const GET: APIRoute = async ({ props }) => {
  const scaledH = Math.round((W * 1080) / 1920);
  const top = Math.min(
    scaledH - H,
    Math.max(0, Math.round((props.focusY as number) * scaledH - H / 2)),
  );
  const jpeg = await sharp(await readFile(resolve(props.path as string)))
    .resize(W, scaledH)
    .extract({ left: 0, top, width: W, height: H })
    .flatten({ background: '#1C1B1A' })
    .jpeg({ quality: 85, mozjpeg: true })
    .toBuffer();
  return new Response(new Uint8Array(jpeg), { headers: { 'Content-Type': 'image/jpeg' } });
};
