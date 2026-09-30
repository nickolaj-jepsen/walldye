/**
 * The plate carried between a grid and its piece's page on navigation, as a cross-document view
 * transition. Only one plate is named at a time: the leaving page names the plate the link was for
 * (pageswap) and records its slug and shape, and the arriving page names its plate for that slug when
 * the shapes match (pagereveal). Anything else skips the transition.
 */

/** The view-transition-name site.css styles. */
export const NAME = 'plate';
const KEY = 'walldye:plate-move';

/** What the leaving page carried: its plate's slug and picture ratio (width over height). */
export interface Carried {
  slug: string;
  ratio: number;
}

/** The slug a site path opens (`/dither-moon` gives `dither-moon`), or null for `/` and deeper paths. */
export function slugOfPath(path: string): string | null {
  const m = /^\/([a-z0-9][a-z0-9-]*)$/.exec(path);
  return m ? m[1] : null;
}

/** Whether two picture ratios are one shape, allowing for their serialization's rounding. */
export function sameShape(a: number, b: number): boolean {
  return Number.isFinite(a) && Number.isFinite(b) && a > 0 && b > 0 && Math.abs(a / b - 1) < 1e-3;
}

/** A plate's picture ratio, width over height: site.css's registered `--ratio`. */
export function plateRatio(plate: HTMLElement): number {
  return Number.parseFloat(getComputedStyle(plate).getPropertyValue('--ratio'));
}

function onScreen(el: Element): boolean {
  const r = el.getBoundingClientRect();
  return r.width > 0 && r.bottom > 0 && r.top < innerHeight;
}

const gridPlate = (doc: Document, slug: string): HTMLElement | null => {
  const plate = doc.querySelector<HTMLElement>(`.grid > li[data-slug="${slug}"] .plate`);
  return plate && onScreen(plate) ? plate : null;
};

/** The plate to carry to `dest`: the grid plate of the piece it opens, or the detail plate when it goes to the index. */
export function leavingPlate(doc: Document, dest: URL): HTMLElement | null {
  if (dest.origin !== location.origin) return null;
  const slug = slugOfPath(dest.pathname);
  if (slug) return gridPlate(doc, slug);
  if (dest.pathname !== '/') return null;
  const plate = doc.querySelector<HTMLElement>('.spread .plate');
  return plate && onScreen(plate) ? plate : null;
}

/** The plate that receives `slug`'s: the detail plate on its page, else its plate in a grid. */
export function arrivingPlate(doc: Document, slug: string): HTMLElement | null {
  return (
    doc.querySelector<HTMLElement>(`.spread .plate[data-plate="${slug}"]`) ?? gridPlate(doc, slug)
  );
}

let named: HTMLElement | null = null;

function name(plate: HTMLElement | null): void {
  if (named) named.style.viewTransitionName = '';
  named = plate;
  if (plate) plate.style.viewTransitionName = NAME;
}

function carry(c: Carried): boolean {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(c));
    return true;
  } catch {
    return false;
  }
}

function carried(): Carried | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    sessionStorage.removeItem(KEY);
    const c = raw ? (JSON.parse(raw) as Partial<Carried>) : null;
    return c && typeof c.slug === 'string' && typeof c.ratio === 'number' ? (c as Carried) : null;
  } catch {
    return null;
  }
}

/** Names the plate the navigation carries away and records it, or skips the transition when there is none. */
export function onPageSwap(e: PageSwapEvent): void {
  const vt = e.viewTransition;
  if (!vt) return;
  const url = e.activation?.entry.url;
  const plate = url ? leavingPlate(document, new URL(url)) : null;
  const slug = plate?.dataset.plate;
  if (!plate || !slug || !carry({ slug, ratio: plateRatio(plate) })) {
    vt.skipTransition();
    return;
  }
  name(plate);
}

/** Names the plate that receives the carried one, or skips the transition when none fits. */
export function onPageReveal(e: PageRevealEvent): void {
  // A page back from the back/forward cache still names what it carried away.
  name(null);
  const vt = e.viewTransition;
  if (!vt) return;
  const from = carried();
  const plate = from ? arrivingPlate(document, from.slug) : null;
  if (!from || !plate || !sameShape(plateRatio(plate), from.ratio)) {
    vt.skipTransition();
    return;
  }
  name(plate);
  vt.finished.finally(() => name(null)).catch(() => {});
}
