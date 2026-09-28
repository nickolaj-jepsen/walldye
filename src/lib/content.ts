/**
 * Helpers over the `wallpapers` collection shared by the pages, the endpoints and (for the pure
 * ones) the client modules: aspects and export sizes, facets, sort order, captions, search text.
 *
 * Runtime-pure: no Node or Astro imports, so client code may import it too.
 */
import type { CollectionEntry } from 'astro:content';
import { FACET_LEGENDS, TAXONOMY_FACETS, UNLISTED, facetLabel, type Facet, type OtherValue } from './labels';

export type Piece = CollectionEntry<'wallpapers'>['data'];
export type Source = Piece['sources'][number];

/** What the tools and `?v=` call the version design.py draws without a named variant. */
export const DEFAULT_VARIANT = 'default';

/** Aspect ratios the site offers (walldye.SITE_ASPECTS, same order). */
export const SITE_ASPECTS = ['16:9', '16:10', '21:9', '32:9', '9:19.5', '10:16'] as const;
export type Aspect = (typeof SITE_ASPECTS)[number];

/** Template canvas per aspect; the short side is 1080. */
export const CANVAS: Record<Aspect, readonly [number, number]> = {
  '16:9': [1920, 1080],
  '16:10': [1728, 1080],
  '21:9': [2520, 1080],
  '32:9': [3840, 1080],
  '9:19.5': [1080, 2340],
  '10:16': [1080, 1728],
};

/** Export sizes per aspect as `<w>x<h>`, smallest first; the panel appends "your screen". */
export const EXPORT_SIZES: Record<Aspect, readonly string[]> = {
  '16:9': ['1920x1080', '2560x1440', '3840x2160', '5120x2880'],
  '16:10': ['1920x1200', '2560x1600', '2880x1800', '3840x2400'],
  '21:9': ['2560x1080', '3440x1440', '5120x2160'],
  '32:9': ['3840x1080', '5120x1440', '7680x2160'],
  '9:19.5': ['1080x2340', '1170x2532', '1290x2796', '1440x3120'],
  '10:16': ['1200x1920', '1600x2560', '2400x3840'],
};

/** Index into EXPORT_SIZES[aspect] of the size selected before the visitor picks one. */
export const DEFAULT_SIZE_INDEX = 1;

/** Export formats: radio value, visible label, file extension. */
export const FORMATS = [
  { value: 'svg', label: 'SVG', ext: 'svg' },
  { value: 'png', label: 'PNG', ext: 'png' },
  { value: 'webp', label: 'WebP', ext: 'webp' },
  { value: 'jpeg', label: 'JPEG', ext: 'jpg' },
] as const;
export const DEFAULT_FORMAT = 'png';

/** '16:9' -> '16x9', the aspect as it appears in template and export file names. */
export function aspectLabel(aspect: string): string {
  return aspect.replace(':', 'x');
}

/** Whether a piece composes natively for every site aspect. */
export function fitsAnyScreen(p: Piece): boolean {
  return SITE_ASPECTS.every((a) => p.aspects.includes(a));
}

/** The computed "Other" facet values that apply to a piece. */
export function otherValues(p: Piece): OtherValue[] {
  const out: OtherValue[] = [];
  if (p.sources.length) out.push('references');
  if (fitsAnyScreen(p)) out.push('any-screen');
  if (p.hasScript) out.push('source-code');
  out.push(p.ai_generated ? 'claude' : 'human-made');
  return out;
}

/** Every `facet:value` pair of a piece, taxonomy and computed; the `data-facets` vocabulary. */
export function facetPairs(p: Piece): string[] {
  return [
    ...TAXONOMY_FACETS.flatMap((f) => p[f].map((v) => `${f}:${v}`)),
    ...otherValues(p).map((v) => `other:${v}`),
  ];
}

/** Index URL filtered to one facet value, in the query format the index form submits. */
export function indexQuery(facet: Facet, value: string): string {
  return `/?${new URLSearchParams({ [facet]: value })}`;
}

export interface FilterEntry {
  value: string;
  label: string;
  count: number;
}
export interface FilterGroup {
  facet: Facet;
  legend: string;
  entries: FilterEntry[];
}

/**
 * The index's filter groups over `pieces`: entries sorted by label, with their unfiltered counts.
 * Entries matching every piece or none are left out (they cannot narrow the grid), as are
 * UNLISTED values; groups left empty are dropped.
 */
export function filterGroups(pieces: Piece[]): FilterGroup[] {
  const facets: Facet[] = [...TAXONOMY_FACETS, 'other'];
  const pairs = pieces.map((p) => new Set(facetPairs(p)));
  const groups: FilterGroup[] = [];
  for (const facet of facets) {
    const values = new Set<string>();
    for (const set of pairs) for (const pair of set) if (pair.startsWith(`${facet}:`)) values.add(pair.slice(facet.length + 1));
    const entries: FilterEntry[] = [];
    for (const value of values) {
      if (facet !== 'other' && UNLISTED[facet].includes(value)) continue;
      const count = pairs.filter((s) => s.has(`${facet}:${value}`)).length;
      if (count === 0 || count === pieces.length) continue;
      entries.push({ value, label: facetLabel(facet, value) ?? value, count });
    }
    entries.sort((a, b) => collator.compare(a.label, b.label));
    if (entries.length) groups.push({ facet, legend: FACET_LEGENDS[facet], entries });
  }
  return groups;
}

const collator = new Intl.Collator('en', { sensitivity: 'base', numeric: true });

export type SortOrder = 'newest' | 'title';

/** The fields the index sorts on; a Piece or an index `li`'s data attributes. */
export interface SortKey {
  slug: string;
  title: string;
  added: string;
}

/** Index order: newest first (added descending) or by title, ties broken by slug. */
export function comparePieces(a: SortKey, b: SortKey, order: SortOrder = 'newest'): number {
  const primary = order === 'title' ? collator.compare(a.title, b.title) : b.added.localeCompare(a.added);
  return primary || (a.slug < b.slug ? -1 : a.slug > b.slug ? 1 : 0);
}

/** Collection entries in index order (comparePieces). */
export function sortPieces<T extends { data: SortKey }>(pieces: T[], order: SortOrder = 'newest'): T[] {
  return pieces.slice().sort((a, b) => comparePieces(a.data, b.data, order));
}

/** Lowercase, accents stripped, curly quotes straightened and whitespace collapsed; applied to both the search text and the query. */
export function normaliseSearch(text: string): string {
  return text
    .normalize('NFD')
    .replace(/\p{M}+/gu, '')
    .replace(/[‘’]/g, "'")
    .replace(/[“”]/g, '"')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim();
}

/** What the index search matches for a piece: title, description and source authors and titles. */
export function searchText(p: Piece): string {
  return normaliseSearch([p.title, p.description, ...p.sources.flatMap((s) => [s.author ?? '', s.title ?? ''])].join(' '));
}

export interface CaptionSource {
  source: Source;
  /** 1-based footnote number of the source in the Sources list. */
  n: number;
}

/**
 * Sources named in the caption: the recreations ("after …"), or when there are none the
 * inspirations ("inspired by …"); reference and data sources appear only as footnotes.
 */
export function captionSources(p: Pick<Piece, 'sources'>): { kind: 'recreation' | 'inspiration'; items: CaptionSource[] } | undefined {
  const numbered = p.sources.map((source, i) => ({ source, n: i + 1 }));
  for (const kind of ['recreation', 'inspiration'] as const) {
    const items = numbered.filter((s) => s.source.kind === kind);
    if (items.length) return { kind, items };
  }
  return undefined;
}

/** One caption source as the text around its italic title. */
export interface CaptionPart {
  /** The list separator, then "{author}, " (or the bare author when there is no title). */
  before: string;
  title?: string;
  lang?: string;
  /** ", {year}" for a recreation with a year, else empty. */
  after: string;
  /** 1-based footnote number. */
  n: number;
}

/**
 * The caption's attribution (docs/design.md, Detail): "after " for recreations or "inspired by " for
 * inspirations, then each source as "{author}, {title}" (recreations add ", {year}"), listed as
 * "A, B and C" with missing fields dropped. A source by the same author as the one before it leaves
 * the name out: "Mark Rothko, No. 61 and Seagram murals". Undefined when no source is captioned.
 */
export function captionParts(p: Pick<Piece, 'sources'>): { lead: string; parts: CaptionPart[] } | undefined {
  const caption = captionSources(p);
  if (!caption) return undefined;
  const { kind, items } = caption;
  const parts = items.map(({ source: s, n }, i) => {
    const sep = i === 0 ? '' : i === items.length - 1 ? ' and ' : ', ';
    const sameAuthor = i > 0 && s.title !== undefined && s.author !== undefined && s.author === items[i - 1].source.author;
    const author = s.author && !sameAuthor ? `${s.author}${s.title ? ', ' : ''}` : '';
    const after = kind === 'recreation' && s.year !== undefined ? `, ${s.year}` : '';
    return { before: sep + author, title: s.title, lang: s.lang, after, n };
  });
  return { lead: kind === 'recreation' ? 'after ' : 'inspired by ', parts };
}

/** "27 September 2026" from an ISO date. */
export function formatAdded(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number);
  return new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' }).format(Date.UTC(y, m - 1, d));
}

/** Number of lines in a source file, not counting a final newline. */
export function lineCount(text: string): number {
  return text.replace(/\n$/, '').split('\n').length;
}

/**
 * The versions the detail page offers, the default included, and how many of them are drafts. The
 * loader keeps draft variants only in `astro dev`, so a production build counts published ones.
 */
export function versionCount(p: Piece): { versions: number; drafts: number } {
  return { versions: Math.max(1, p.versions.length), drafts: p.versions.filter((v) => v.draft).length };
}

/** `<slug>`, or `<slug>--<variant>` for a named variant; neither contains `--`, so the name splits back. */
export function fileStem(slug: string, variant: string): string {
  return variant === DEFAULT_VARIANT ? slug : `${slug}--${variant}`;
}

/** Export file name (docs/design.md, Export): `<stem>-<token>-<w>x<h>.<ext>`, or for SVG `<stem>-<token>-<aspect>[-crop].svg`, the stem from fileStem. */
export function downloadName(
  slug: string,
  variant: string,
  token: string,
  format: (typeof FORMATS)[number],
  size: string,
  aspect: string,
  cropped: boolean,
): string {
  const stem = fileStem(slug, variant);
  if (format.value === 'svg') return `${stem}-${token}-${aspectLabel(aspect)}${cropped ? '-crop' : ''}.svg`;
  return `${stem}-${token}-${size}.${format.ext}`;
}
