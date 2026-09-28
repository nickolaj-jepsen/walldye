/** Shared helpers for the Playwright specs (not a spec: playwright.config.ts matches `*.spec.ts`). */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { expect, type Page } from '@playwright/test';
import { decode } from 'fast-png';
import { DEFAULT_LICENSE, isDraft, licenseOf, namedVariants, smartQuotes } from '../../src/lib/meta';
import type { Slots, SlotsEntry } from '../../src/lib/recolour';
import { findColours, skeleton } from '../../src/lib/tokenize';
import { loadMeta, slugs } from '../catalogue';

export const ROOT = fileURLToPath(new URL('../../', import.meta.url));

/** A repo file as text. */
export const readText = (rel: string): string => readFileSync(`${ROOT}${rel}`, 'utf8');

/** A version's build/slots.json (build/<variant>/ for a named one), as `walldye build` wrote it. */
export const slotsOf = (slug: string, variant = 'default'): Slots =>
  JSON.parse(readText(`wallpapers/${slug}/build/${variant === 'default' ? '' : `${variant}/`}slots.json`)) as Slots;

/** The served URL of a version's dark template at `aspect`, /t/<sha256[:12]>.svg. */
export const templateUrl = (slots: Slots, aspect: string): string => `/t/${(slots[`${aspect}/dark`] as SlotsEntry).sha256.slice(0, 12)}.svg`;

export interface CatalogueVersion {
  name: string;
  /** As the page sets it, quotes curled. */
  label: string;
  /** The version's own description, else the piece's, quotes curled. */
  description: string;
  slots: Slots;
  /** The aspects with templates of their own; any other shape is a crop of 16:9. */
  aspects: string[];
}

export interface CataloguePiece {
  slug: string;
  description: string;
  license: string;
  franchise?: { title: string; owner: string };
  /** The published versions, default first. */
  versions: CatalogueVersion[];
}

/** Every published piece with its published versions, from meta.yaml and the built slots.json. */
export function publishedPieces(): CataloguePiece[] {
  return slugs(ROOT).flatMap((slug) => {
    const meta = loadMeta(ROOT, slug);
    if (isDraft(meta)) return [];
    const description = smartQuotes(String(meta.description));
    const unnamed = (meta.variants as Record<string, { label?: string }> | undefined)?.default;
    const named = namedVariants(meta).filter((v) => !v.draft);
    const versions = [{ name: 'default', label: unnamed?.label, description: undefined }, ...named].map((v) => {
      const slots = slotsOf(slug, v.name);
      return {
        name: v.name,
        label: smartQuotes(String(v.label ?? '')),
        description: typeof v.description === 'string' ? smartQuotes(v.description) : description,
        slots,
        aspects: Object.keys(slots).filter((k) => k.endsWith('/dark')).map((k) => k.split('/')[0]),
      };
    });
    const f = meta.franchise as CataloguePiece['franchise'];
    const franchise = f && { title: smartQuotes(f.title), owner: smartQuotes(f.owner) };
    return [{ slug, description, license: String(licenseOf(meta) ?? DEFAULT_LICENSE), franchise, versions }];
  });
}

export interface Manifest {
  themes: string[];
  renders: { slug: string; aspect: string; theme: string; entry: string; template: string; sha256: string; render: string }[];
  resvg: { svg: string; png: string; width: number; height: number; background: string; resvg_py: string };
}

/** tests/fixtures/manifest.json: the Python reference renders and the resvg-py reference PNG. */
export const MANIFEST = JSON.parse(readText('tests/fixtures/manifest.json')) as Manifest;

/** The pieces with Python reference renders under tests/fixtures. */
export const REFERENCE_PIECES = ['dither-moon', 'radar-sweep', 'schotter'] as const;

export interface Rgb {
  width: number;
  height: number;
  /** 3 bytes per pixel. */
  data: Uint8Array;
}

/** A PNG as 8-bit RGB (alpha dropped: every surface compared here is opaque). */
export function decodeRgb(png: Uint8Array): Rgb {
  const img = decode(png);
  expect(img.depth).toBe(8);
  const n = img.width * img.height;
  const step = img.channels;
  const data = new Uint8Array(n * 3);
  for (let i = 0; i < n; i++) {
    const g = step < 3;
    data[i * 3] = img.data[i * step];
    data[i * 3 + 1] = img.data[i * step + (g ? 0 : 1)];
    data[i * 3 + 2] = img.data[i * step + (g ? 0 : 2)];
  }
  return { width: img.width, height: img.height, data };
}

export interface PixelDiff {
  /** Largest difference in any channel. */
  max: number;
  /** Mean absolute difference per channel. */
  mean: number;
  /** Channels differing by more than 1. */
  overOne: number;
}

/** Per-channel difference between two images of the same size. */
export function pixelDiff(a: Rgb, b: Rgb): PixelDiff {
  expect([a.width, a.height]).toEqual([b.width, b.height]);
  let max = 0;
  let sum = 0;
  let overOne = 0;
  for (let i = 0; i < a.data.length; i++) {
    const d = Math.abs(a.data[i] - b.data[i]);
    if (d > max) max = d;
    if (d > 1) overOne++;
    sum += d;
  }
  return { max, mean: sum / a.data.length, overOne };
}

/** The `#RRGGBB` of the pixel at `x`, `y`. */
export function pixelHex(img: Rgb, x: number, y: number): string {
  const i = (y * img.width + x) * 3;
  return `#${[...img.data.subarray(i, i + 3)].map((v) => v.toString(16).padStart(2, '0')).join('')}`.toUpperCase();
}

/** Largest per-channel difference between two colours. */
export function colourDistance(a: string, b: string): number {
  let worst = 0;
  for (let k = 1; k < 7; k += 2) worst = Math.max(worst, Math.abs(parseInt(a.slice(k, k + 2), 16) - parseInt(b.slice(k, k + 2), 16)));
  return worst;
}

/** Largest per-channel difference between the colour slots of two SVGs, which must share a skeleton. */
export function maxSlotError(a: string, b: string): number {
  expect(skeleton(a)).toBe(skeleton(b));
  const ca = findColours(a).map((s) => s[2]);
  const cb = findColours(b).map((s) => s[2]);
  expect(ca.length).toBe(cb.length);
  return ca.reduce((worst, c, i) => Math.max(worst, colourDistance(c, cb[i])), 0);
}

/** Text of the SVG the index plate of `slug` shows, or null while it has no single loaded image. */
export async function plateSvg(page: Page, slug: string): Promise<string | null> {
  return page.evaluate(async (s) => {
    const imgs = document.querySelectorAll<HTMLImageElement>(`.grid > li[data-slug="${s}"] .plate > img`);
    if (imgs.length !== 1 || !imgs[0].complete) return null;
    return (await fetch(imgs[0].src)).text();
  }, slug);
}

/**
 * Brings each plate of `svgs` near the view, where the index loads it, and waits until it shows
 * exactly that SVG text (a blob: recolour, or the template itself when that is unchanged).
 */
export async function platesSettled(page: Page, svgs: Record<string, string>): Promise<void> {
  for (const [slug, svg] of Object.entries(svgs)) {
    await page.locator(`.grid > li[data-slug="${slug}"]`).scrollIntoViewIfNeeded();
    await expect.poll(async () => (await plateSvg(page, slug)) === svg, { message: `the ${slug} plate shows its recolour`, timeout: 10_000 }).toBe(true);
  }
}

/**
 * Anything that sticks out past the viewport's sides: the page's own horizontal scroll, and every
 * rendered element whose box crosses the left or right edge outside a scroll or clip container.
 */
export async function horizontalOverflow(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const doc = document.documentElement;
    const vw = doc.clientWidth;
    const bad: string[] = [];
    if (doc.scrollWidth > vw) bad.push(`page scrolls sideways: ${doc.scrollWidth} > ${vw}`);
    const clipped = (el: Element): boolean => {
      for (let p = el.parentElement; p && p !== document.body && p !== doc; p = p.parentElement) {
        if (getComputedStyle(p).overflowX !== 'visible') return true;
      }
      return false;
    };
    const name = (el: Element) => `${el.tagName.toLowerCase()}${el.id ? `#${el.id}` : ''}${el.className && typeof el.className === 'string' ? `.${el.className.trim().split(/\s+/).join('.')}` : ''}`;
    for (const el of document.body.querySelectorAll('*')) {
      if (el.closest('noscript, template, .vh') || el.matches('script, style')) continue;
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue;
      if ((r.right > vw + 0.5 || r.left < -0.5) && !clipped(el)) bad.push(`${name(el)} spans ${Math.round(r.left)}..${Math.round(r.right)} of ${vw}`);
    }
    return bad;
  });
}
