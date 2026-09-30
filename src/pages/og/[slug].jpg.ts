import { getCollection } from 'astro:content';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import type { APIRoute, GetStaticPaths } from 'astro';
import sharp from 'sharp';
import { CANVAS } from '../../lib/content';
import { cropBox, focusPosition } from '../../lib/shape';
import { FIREPROOF } from '../../lib/theme';

const W = 1200;
const H = 630;
const ASPECT = `${W}:${H}`;
const [, CANVAS_H] = CANVAS['16:9'];

/** Social card: a 1200x630 band of the fireproof 16:9 template, centered on its focus where the band can move. */
export const getStaticPaths = (async () =>
  (await getCollection('wallpapers')).map(({ data }) => ({
    params: { slug: data.slug },
    props: { path: data.templates['16:9/dark'].path, focus: data.focus },
  }))) satisfies GetStaticPaths;

export const GET: APIRoute = async ({ props }) => {
  const box = cropBox(ASPECT, focusPosition(ASPECT, props.focus as [number, number]));
  const scale = W / box.w;
  const scaledH = Math.round(CANVAS_H * scale);
  const top = Math.min(scaledH - H, Math.round(box.y * scale));
  const jpeg = await sharp(await readFile(resolve(props.path as string)))
    .resize(W, scaledH)
    .extract({ left: 0, top, width: W, height: H })
    .flatten({ background: FIREPROOF.bg })
    .jpeg({ quality: 85, mozjpeg: true })
    .toBuffer();
  return new Response(new Uint8Array(jpeg), { headers: { 'Content-Type': 'image/jpeg' } });
};
