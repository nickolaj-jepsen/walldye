'use client';
/**
 * The detail page's state for its client components: the version, shape, crop and motif placement
 * the address holds (nuqs), the export choices of size and format, and what follows from them.
 * `<DetailLocal>` holds what the address does not and wraps the whole page. Each part that reads the
 * state renders twice: inside `<DetailDefaults>` as the Suspense fallback the prerender keeps, and
 * inside `<DetailFromAddress>`, which reads the query string once the browser renders it. A page
 * may have several such parts; they share the address and DetailLocal, so they agree.
 */
import { useQueryStates } from 'nuqs';
import {
  createContext,
  type ReactNode,
  type RefObject,
  Suspense,
  use,
  useMemo,
  useRef,
  useState,
} from 'react';
import { NARROW_QUERY } from '../../client/screen';
import { useTheme } from '../../client/theme/use-theme';
import type { PlateData } from '../../lib/catalog';
import { type Aspect, DEFAULT_FORMAT, DEFAULT_VARIANT, FORMATS } from '../../lib/content';
import type { MotifInfo, Placement } from '../../lib/motif';
import { DEFAULT_PRESET } from '../../lib/presets';
import { type ExportShape, nearestAspect, withinLimits } from '../../lib/shape';
import { detailKeys, detailParams } from './address';
import {
  cropsInPlace,
  type DetailState,
  keptCrop,
  placementOf,
  shapeOf,
  sizeFor,
  sizePx,
} from './state';
import { useMedia, useScreenPx } from './use-screen';

/** One version as the detail page's client needs it. */
export interface DetailVersion {
  /** `default` or the variant name. */
  name: string;
  label: string;
  description: string;
  alt: string;
  focus: readonly [number, number];
  /** Each shape the piece composes for, resolved; any other shape is a crop of 16:9. */
  plates: Partial<Record<Aspect, PlateData>> & Record<'16:9', PlateData>;
}

/** What the server hands the detail page's client components. */
export interface DetailPiece {
  slug: string;
  title: string;
  /** The resolved license id. */
  license: string;
  /** Shapes the piece composes for. */
  aspects: Aspect[];
  motif: boolean;
  /** The default first, then the named variants; at least the default. */
  versions: DetailVersion[];
  /** Whether the piece shows named versions to switch between. */
  named: boolean;
}

export type Format = (typeof FORMATS)[number];

/** What the address holds; null where it says nothing (or nothing valid). */
interface Address {
  variant: string | null;
  aspect: Aspect | null;
  crop: number | null;
  at: [number, number] | null;
  scale: number | null;
}

export interface Detail {
  piece: DetailPiece;
  /** The shown version: the address's when the piece has it, else the default. */
  version: DetailVersion;
  state: DetailState;
  /** Whether the piece composes for the chosen shape; otherwise it is a crop of 16:9. */
  native: boolean;
  /** The template shape the plate and the export read: the chosen shape's own, else 16:9. */
  source: Aspect;
  /** The shown version's templates for `source`. */
  data: PlateData;
  /** The motif of `data` in the applied regime, for a piece that has one. */
  motif: MotifInfo | undefined;
  /** The visitor's placement, clamped; null leaves the motif where the design drew it. */
  placement: Placement | null;
  /** Export geometry: shape, crop position (the focus until placed) and placement. */
  shape: ExportShape;
  /** Narrow screens (site.css's stacked layout); false before hydration. */
  narrow: boolean;
  /** Whether the plate shows the crop itself (narrow screens, tall cropped shapes). */
  inPlace: boolean;
  /** The screen in output pixels; 1920×1080 before hydration. */
  screenPx: readonly [number, number];
  /** The site shape nearest the screen. */
  screenAspect: Aspect;
  /** The applied theme's token; the default preset's before hydration. */
  token: string;
  /** The checked size radio: `<w>x<h>` or `screen`. */
  size: string;
  format: Format;
  /** Whether this browser can draw a file at a size radio's value. */
  allowed: (size: string) => boolean;
  chooseVersion: (name: string) => void;
  /** Switches shape; the size follows, the motif goes back to that shape's own place and a crop is kept only along the same axis. */
  chooseAspect: (next: Aspect) => void;
  /** Picking "your screen" also switches to the screen's shape. */
  chooseSize: (size: string) => void;
  chooseFormat: (format: Format) => void;
  setCrop: (t: number) => void;
  /** Writes the motif's anchor and size; a size of 1 is written as none. */
  setMotif: (patch: { at?: [number, number] | null; scale?: number | null }) => void;
  /** The export: the panel puts its runner in `run` and reports `busy`; the label's Download calls it. */
  download: {
    busy: boolean;
    setBusy: (busy: boolean) => void;
    run: RefObject<((from: HTMLElement) => void) | null>;
  };
}

const DetailContext = createContext<Detail | null>(null);

interface Preview {
  /** The placement a drag shows before it is written to the address. */
  preview: Placement | null;
  setPreview: (p: Placement | null) => void;
}

const PreviewContext = createContext<Preview | null>(null);

/** The page's state that the address does not hold. */
interface Local {
  sizeChoice: string | null;
  setSizeChoice: (size: string) => void;
  format: Format;
  chooseFormat: (format: Format) => void;
  busy: boolean;
  setBusy: (busy: boolean) => void;
  run: RefObject<((from: HTMLElement) => void) | null>;
}

const LocalContext = createContext<Local | null>(null);

/** The state of a detail page the address does not hold; wraps every detail provider of the page. */
export function DetailLocal({ children }: { children: ReactNode }) {
  const [sizeChoice, setSizeChoice] = useState<string | null>(null);
  const [format, chooseFormat] = useState<Format>(
    () => FORMATS.find((f) => f.value === DEFAULT_FORMAT) ?? FORMATS[1],
  );
  const [busy, setBusy] = useState(false);
  const run = useRef<((from: HTMLElement) => void) | null>(null);
  const [preview, setPreview] = useState<Placement | null>(null);
  return (
    <LocalContext value={{ sizeChoice, setSizeChoice, format, chooseFormat, busy, setBusy, run }}>
      <PreviewContext value={{ preview, setPreview }}>{children}</PreviewContext>
    </LocalContext>
  );
}

/** The detail page's state; throws outside a detail provider. */
export function useDetail(): Detail {
  const d = use(DetailContext);
  if (!d) throw new Error('useDetail() needs <DetailFromAddress> or <DetailDefaults>');
  return d;
}

/** The motif placement a drag is showing; kept apart so a drag re-renders only its readers. */
export function useMotifPreview(): Preview {
  const p = use(PreviewContext);
  if (!p) throw new Error('useMotifPreview() needs <DetailLocal>');
  return p;
}

const FALLBACK_PX: readonly [number, number] = [1920, 1080];
const NO_ADDRESS: Address = { variant: null, aspect: null, crop: null, at: null, scale: null };

function useDetailValue(
  piece: DetailPiece,
  address: Address,
  write: (patch: Partial<Address>) => void,
): Detail {
  const narrow = useMedia(NARROW_QUERY) ?? false;
  const px = useScreenPx();
  const theme = useTheme();
  const local = use(LocalContext);
  if (!local) throw new Error('a detail provider needs <DetailLocal> above it');
  const { sizeChoice, setSizeChoice, format, chooseFormat, busy, setBusy, run } = local;

  const screen = px ?? FALLBACK_PX;
  const screenAspect = nearestAspect(...screen);
  // The page starts in the screen's shape, unless the screen is too large to draw at its size.
  const startAspect: Aspect = px && withinLimits(...px) ? screenAspect : '16:9';
  const native = useMemo(() => new Set<string>(piece.aspects), [piece.aspects]);
  const version = piece.versions.find((v) => v.name === address.variant) ?? piece.versions[0];
  const aspect = address.aspect ?? startAspect;
  const state: DetailState = {
    variant: version.name,
    aspect,
    crop: address.crop,
    at: address.at,
    scale: address.scale,
  };
  const source: Aspect = native.has(aspect) ? aspect : '16:9';
  const data = version.plates[source] ?? version.plates['16:9'];
  const motif = data[theme?.regime ?? 'dark'].motif;
  const shape = shapeOf(state, native, version.focus, motif);
  const allowed = (size: string) => withinLimits(...sizePx(size, screen));
  const startKeep = px && aspect === screenAspect ? 'screen' : '';
  const size = sizeFor(aspect, sizeChoice ?? startKeep, allowed);

  const switchAspect = (next: Aspect, keep: string) => {
    write({
      // The address names the shape unless it is 16:9 where the page would start in 16:9 anyway.
      aspect: next === '16:9' && startAspect === '16:9' ? null : next,
      crop: keptCrop(state, next, native),
      at: null,
    });
    setSizeChoice(keep);
  };

  return {
    piece,
    version,
    state,
    native: native.has(aspect),
    source,
    data,
    motif,
    placement: placementOf(state, motif),
    shape,
    narrow,
    inPlace: cropsInPlace(shape, narrow),
    screenPx: screen,
    screenAspect,
    token: theme?.token ?? DEFAULT_PRESET.name,
    size,
    format,
    allowed,
    chooseVersion: (name) => write({ variant: name === DEFAULT_VARIANT ? null : name }),
    chooseAspect: (next) =>
      switchAspect(next, size === 'screen' && next === screenAspect ? 'screen' : ''),
    chooseSize: (value) => {
      if (value === 'screen' && aspect !== screenAspect) switchAspect(screenAspect, 'screen');
      else setSizeChoice(value);
    },
    chooseFormat,
    setCrop: (t) => write({ crop: t }),
    setMotif: ({ at, scale }) =>
      write({
        ...(at !== undefined && { at }),
        ...(scale !== undefined && { scale: scale === 1 ? null : scale }),
      }),
    download: { busy, setBusy, run },
  };
}

/** The detail state read from and written to the address. Reads search params: keep it under `<Suspense>`. */
export function DetailFromAddress({
  piece,
  children,
}: {
  piece: DetailPiece;
  children: ReactNode;
}) {
  const [address, setAddress] = useQueryStates(detailParams, {
    history: 'replace',
    scroll: false,
    urlKeys: detailKeys,
  });
  const value = useDetailValue(piece, address, (patch) => {
    void setAddress(patch);
  });
  return <DetailContext value={value}>{children}</DetailContext>;
}

/** The detail state at its start, with no address: the prerendered fallback of `<DetailFromAddress>`. */
export function DetailDefaults({ piece, children }: { piece: DetailPiece; children: ReactNode }) {
  const value = useDetailValue(piece, NO_ADDRESS, () => {});
  return <DetailContext value={value}>{children}</DetailContext>;
}

/**
 * A part of the page that reads the detail state: `children` in the start state while prerendered,
 * then in the address's state in the browser. Keep these parts small: the browser draws each one
 * again in full rather than hydrating it.
 */
export function DetailPart({ piece, children }: { piece: DetailPiece; children: ReactNode }) {
  return (
    <Suspense fallback={<DetailDefaults piece={piece}>{children}</DetailDefaults>}>
      <DetailFromAddress piece={piece}>{children}</DetailFromAddress>
    </Suspense>
  );
}
