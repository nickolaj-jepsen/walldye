/**
 * The catalog's types, as scripts/codegen.ts writes src/generated/catalog.json, and pure helpers
 * over them. No Node, Next or JSON imports, so client code may import it; server code reads the
 * data through src/server/catalog.ts.
 */
import type { Aspect } from './content';
import type { TaxonomyFacet } from './labels';
import type { MotifInfo } from './motif';
import type { Regime } from './theme';

/**
 * One shape's templates: the var template hash for each regime. Both hold the same hash when one
 * build file serves both regimes (the `--dk`/`--lt` switches pick the rows), which is the usual case.
 */
export interface PlateRef {
  dark: string;
  light: string;
}

/** Templates by shape: always 16:9, plus each other shape the piece composes for. */
export type Plates = Partial<Record<Aspect, PlateRef>> & Record<'16:9', PlateRef>;

/** What a page needs to show a var template, `/t/<hash>.svg`. */
export interface TemplateInfo {
  /**
   * The file has `<defs>`. External `<use>` resolves paint servers, masks and clip paths inside the
   * file, out of reach of the page's variables (and WebKit drops masks and clips there), so the
   * plate fetches the text and inlines it for a same-document `<use>`.
   */
  inline: boolean;
  /** Canvas size in template units: the viewBox is `0 0 w h`. */
  canvas: readonly [number, number];
  /** The motif a visitor may move, for a piece that has one; same per regime. */
  motif?: MotifInfo;
}

/** A template with its hash, as a Plate takes it. */
export interface ResolvedTemplate extends TemplateInfo {
  hash: string;
}

/** What a Plate shows: one shape's template for each regime (the same one when shared). */
export interface PlateData {
  dark: ResolvedTemplate;
  light: ResolvedTemplate;
}

export interface Source {
  kind: 'recreation' | 'inspiration' | 'reference' | 'data';
  /** The name of a work, set in italics. */
  title?: string;
  /** The name of anything that is not a work, set upright. */
  topic?: string;
  author?: string;
  year?: number | string;
  url?: string;
  /** BCP 47 language of a foreign title or topic. */
  lang?: string;
}

/** One version of a piece: the default or a named variant. */
export interface Version {
  /** `default` or the variant name (`?v=`). */
  name: string;
  label: string;
  /** The variant's own description, else the piece's. */
  description: string;
  /** The variant's own alt text, else the piece's. */
  alt: string;
  draft: boolean;
  /** Ink-weighted centroid of the 16:9 template, each 0..1. */
  focus: readonly [number, number];
  /** Templates of each shape the piece composes for; any other shape is a crop of 16:9. */
  plates: Plates;
}

/** One wallpaper: meta.yaml in the shape pages read, typeset, plus what codegen attaches. */
export interface Piece {
  slug: string;
  title: string;
  description: string;
  alt: string;
  /** The notes Markdown rendered and typeset (italics, abbr, lining figures), or null. */
  notesHtml: string | null;
  technique: string[];
  subject: string[];
  lineage: string[];
  sources: Source[];
  /** ISO date. */
  added: string;
  /** Who made a human-made piece; a piece a model made has `model` instead. */
  author?: string;
  /** The model id that made the piece; its credit name is in the taxonomy's `models`. */
  model?: string;
  license?: string;
  franchise?: { title: string; owner: string };
  draft: boolean;
  /** `license`, the fan-work id with a `franchise`, or CC0-1.0 for a model-made piece without a recreation. */
  resolvedLicense: string;
  /** Whether design.py exists; legacy pieces have none. Its text is in getScript(). */
  hasScript: boolean;
  hasData: boolean;
  /** Shapes the piece composes for, in SITE_ASPECTS order; the rest are crops of 16:9. */
  aspects: Aspect[];
  /** The default version's focus. */
  focus: readonly [number, number];
  /** Whether the templates hold a motif a visitor may move and resize. */
  motif: boolean;
  /** The default version's templates. */
  plates: Plates;
  /**
   * The versions a visitor can switch between, the default first and then the named variants in
   * meta.yaml order (drafts only in draft builds); [] when no named variant is shown.
   */
  versions: Version[];
  /** Every recorded page view. */
  views: number;
  /** Page views weighted towards recent days, rounded to 0.01. */
  recent: number;
  /** Place on featured.yaml, from 0; absent when the piece is not on it. */
  featured?: number;
}

/** taxonomy.yaml: the words visitors see for each facet value, and each model id's credit name. */
export interface Taxonomy {
  facets: Record<TaxonomyFacet, Record<string, string>>;
  models: Record<string, string>;
}

export interface Catalog {
  /** Sorted by slug. */
  pieces: Piece[];
  /** Every var template the pieces name, by hash. */
  templates: Record<string, TemplateInfo>;
  taxonomy: Taxonomy;
  /** Whether draft pieces and variants were included. */
  drafts: boolean;
}

/** The default version as a Version, whether or not the piece has named variants. */
export function defaultVersion(p: Piece): Version {
  return (
    p.versions[0] ?? {
      name: 'default',
      label: '',
      description: p.description,
      alt: p.alt,
      draft: false,
      focus: p.focus,
      plates: p.plates,
    }
  );
}

/** The versions a visitor can switch between, at least the default. */
export function allVersions(p: Piece): Version[] {
  return p.versions.length ? p.versions : [defaultVersion(p)];
}

/** The version named `name`, else the default. */
export function versionOf(p: Piece, name: string | null | undefined): Version {
  return allVersions(p).find((v) => v.name === name) ?? defaultVersion(p);
}

/** The id of a template part inside its file: `t<hash>-base` or `t<hash>-motif`. */
export function partId(hash: string, part: 'base' | 'motif'): string {
  return `t${hash}-${part}`;
}

/** Where a var template is served. */
export function templateUrl(hash: string): string {
  return `/t/${hash}.svg`;
}

/** The hash of `plate`'s template for `regime`. */
export function plateHash(plate: PlateRef, regime: Regime): string {
  return plate[regime];
}

/** Whether one var template serves both regimes, so the plate needs a single `<use>`. */
export function sharedPlate(plate: PlateRef): boolean {
  return plate.dark === plate.light;
}
