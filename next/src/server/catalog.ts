/**
 * Data access for server components: the generated catalog behind `'use cache'` functions with the
 * `catalog` lifetime (next.config.ts), which never revalidates, so every page stays prerendered.
 * The catalog is imported, since the OpenNext Worker has no file system. Export rows and design.py
 * are read from disk instead, which keeps them out of the Worker: only prerendered pages use them, and
 * `next build` renders every page, while an unknown slug reaches notFound() first.
 */
import 'server-only';
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { cacheLife } from 'next/cache';
import catalogJson from '../generated/catalog.json';
import type { Catalog, Piece, PlateData, PlateRef, ResolvedTemplate } from '../lib/catalog';
import type { Facet } from '../lib/labels';
import { OTHER_LABELS, type OtherValue } from '../lib/labels';
import type { BakeRows } from '../lib/template-vars';

const catalog = catalogJson as unknown as Catalog;

/** Every piece the build shows, sorted by slug. */
export async function getPieces(): Promise<Piece[]> {
  'use cache';
  cacheLife('catalog');
  return catalog.pieces;
}

/** The piece with `slug`, or undefined. */
export async function getPiece(slug: string): Promise<Piece | undefined> {
  'use cache';
  cacheLife('catalog');
  return catalog.pieces.find((p) => p.slug === slug);
}

/** Every slug, for generateStaticParams. */
export async function getSlugs(): Promise<string[]> {
  'use cache';
  cacheLife('catalog');
  return catalog.pieces.map((p) => p.slug);
}

/** The template facts a Plate needs for `ref`, with the hashes folded in. */
export function resolvePlate(ref: PlateRef): PlateData {
  const one = (hash: string): ResolvedTemplate => ({ hash, ...catalog.templates[hash] });
  return { dark: one(ref.dark), light: one(ref.light) };
}

/** The words visitors see for a facet value, or undefined when it has none. */
export function facetLabel(facet: Facet, value: string): string | undefined {
  if (facet === 'other') return OTHER_LABELS[value as OtherValue];
  return catalog.taxonomy.facets[facet][value];
}

/** The credit name of a model id, or undefined. */
export function modelName(model: string): string | undefined {
  return catalog.taxonomy.models[model];
}

/** Whether this build includes drafts (dev, or WALLDYE_DRAFTS=1 at codegen). */
export function hasDrafts(): boolean {
  return catalog.drafts;
}

const GENERATED = join(process.cwd(), 'src', 'generated');

let allRows: Promise<Record<string, BakeRows>> | undefined;

/** The export rows of the templates `hashes` name, for the detail page's client export. */
export async function getRows(hashes: readonly string[]): Promise<Record<string, BakeRows>> {
  'use cache';
  cacheLife('catalog');
  allRows ??= readFile(join(GENERATED, 'rows.json'), 'utf8').then((t) => JSON.parse(t));
  const all = await allRows;
  return Object.fromEntries(hashes.map((h) => [h, all[h]]));
}

/** design.py of `slug`, or null for a legacy piece. */
export async function getScript(slug: string): Promise<string | null> {
  'use cache';
  cacheLife('catalog');
  if (!catalog.pieces.some((p) => p.slug === slug && p.hasScript)) return null;
  return readFile(join(GENERATED, 'scripts', `${slug}.py`), 'utf8');
}
