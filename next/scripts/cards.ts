/**
 * Prebuild, after codegen: draws each piece's social card into public/og/<slug>.png, 1200x630, a
 * band of its default 16:9 template in fireproof centered on the piece's focus where the band can
 * move. next/og (satori and resvg) draws it here rather than in an opengraph-image route, which
 * would put resvg's wasm and a second copy of the catalog into the Worker, past the free plan's
 * size limit.
 *
 * Incremental: a card whose template and focus are unchanged since the last run (recorded in
 * src/generated/.cards-cache.json) is kept. Cards of pieces no longer in the catalog are removed.
 *
 * Usage: tsx scripts/cards.ts
 */
import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { ImageResponse } from 'next/og';
import { createElement } from 'react';
import type { Catalog } from '../src/lib/catalog';
import { CARD_H, CARD_W } from '../src/lib/og-card';
import { cropBox, focusPosition, setRoot } from '../src/lib/shape';
import { type BakeRows, bake } from '../src/lib/template-vars';
import { PRESETS } from '../src/lib/theme';

/** Bumped whenever the drawing changes, so every card is drawn again. */
const CARD_FORMAT = 1;

const APP = resolve(import.meta.dirname, '..');
const OUT = join(APP, 'public', 'og');
const GENERATED = join(APP, 'src', 'generated');
const CACHE = join(GENERATED, '.cards-cache.json');
const ASPECT = `${CARD_W}:${CARD_H}`;

/** The 16:9 var template `svg` baked in fireproof and cut to the card's band around `focus`. */
function cardSvg(svg: string, rows: BakeRows, focus: readonly [number, number]): string {
  const box = cropBox(ASPECT, focusPosition(ASPECT, focus));
  return setRoot(bake(svg, rows, PRESETS.fireproof), box, CARD_W, CARD_H);
}

async function drawCard(svg: string): Promise<Uint8Array> {
  const picture = `data:image/svg+xml;base64,${Buffer.from(svg).toString('base64')}`;
  // fireproof's ground shows through any transparent part of the picture.
  const card = createElement(
    'div',
    { style: { display: 'flex', width: '100%', height: '100%', background: PRESETS.fireproof.bg } },
    createElement('img', { src: picture, width: CARD_W, height: CARD_H, alt: '' }),
  );
  const res = new ImageResponse(card, { width: CARD_W, height: CARD_H });
  return new Uint8Array(await res.arrayBuffer());
}

function readJson<T>(path: string, fallback: T): T {
  try {
    return JSON.parse(readFileSync(path, 'utf8')) as T;
  } catch {
    return fallback;
  }
}

async function main(): Promise<void> {
  const catalog = readJson<Catalog | null>(join(GENERATED, 'catalog.json'), null);
  if (!catalog) throw new Error('src/generated/catalog.json is missing: run `pnpm codegen` first');
  const rows = readJson<Record<string, BakeRows>>(join(GENERATED, 'rows.json'), {});
  const cache = readJson<Record<string, string>>(CACHE, {});
  const next: Record<string, string> = {};
  mkdirSync(OUT, { recursive: true });

  let drawn = 0;
  for (const p of catalog.pieces) {
    const hash = p.plates['16:9'].dark;
    const key = `${CARD_FORMAT}:${hash}:${p.focus.join(',')}`;
    const file = join(OUT, `${p.slug}.png`);
    next[p.slug] = key;
    if (cache[p.slug] === key && existsSync(file)) continue;
    const template = readFileSync(join(APP, 'public', 't', `${hash}.svg`), 'utf8');
    writeFileSync(file, await drawCard(cardSvg(template, rows[hash], p.focus)));
    drawn++;
  }

  let removed = 0;
  for (const name of readdirSync(OUT)) {
    if (name.endsWith('.png') && !(name.slice(0, -4) in next)) {
      rmSync(join(OUT, name));
      removed++;
    }
  }
  writeFileSync(CACHE, JSON.stringify(next));
  console.log(`cards: ${drawn} drawn, ${catalog.pieces.length - drawn} kept, ${removed} removed`);
}

await main();
