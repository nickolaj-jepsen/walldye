/**
 * A grid of plates as Plate.astro renders them (the index, and "See also" on the detail page): each
 * recolored in the current theme while it is within a viewport of the view, shown in the grid's
 * shape, its link opening the piece in that shape.
 */
import { type Aspect, aspectLabel } from '../lib/content';
import { type Seeds, tokenOf } from '../lib/theme';
import { must } from './dom';
import { cropAxis, focusPosition } from './export/shape';
import { keepShowing, type PlateData, plateData } from './plates';
import { deviceAspect } from './screen';
import { currentSeeds, onThemeChange } from './theme/current';

interface GridPlate {
  slug: string;
  link: HTMLAnchorElement;
  plate: HTMLElement;
  data: PlateData;
  /** Shapes with a template of their own; any other is a crop of 16:9. */
  native: ReadonlySet<string>;
  /** The 16:9 template's focus, fractions of the canvas. */
  focus: [number, number];
}

export interface PlateGrid {
  setShape(shape: Aspect): void;
}

/**
 * Shows the plates of `root`'s `.grid` in `shape`, which `root` carries as `data-shape` for site.css.
 * A plate without a template of that shape shows its 16:9 template cropped around its focus, as an
 * export in that shape would.
 */
export function plateGrid(root: HTMLElement, shape: Aspect): PlateGrid {
  const lis = must('.grid', root).querySelectorAll<HTMLLIElement>(':scope > li');
  const items = new Map<Element, GridPlate>(
    [...lis].map((li) => {
      const plate = must('.plate', li);
      const [fx, fy] = (li.dataset.focus ?? '').split(' ').map(Number);
      return [
        li,
        {
          slug: li.dataset.slug ?? '',
          link: must<HTMLAnchorElement>(':scope > a', li),
          plate,
          data: plateData(plate),
          native: new Set((li.dataset.aspects ?? '16:9').split(' ')),
          focus: [Number.isFinite(fx) ? fx : 0.5, Number.isFinite(fy) ? fy : 0.5],
        },
      ];
    }),
  );
  const home = deviceAspect();
  let seeds: Seeds = currentSeeds();
  let token = tokenOf(seeds);
  /** Items within one viewport of the visible area. */
  const near = new Set<GridPlate>();
  /** What each plate shows: `<token> <template aspect>`. */
  const shown = new WeakMap<GridPlate, string>();
  /** The load under way for a plate, and what it is for. */
  const jobs = new Map<GridPlate, { key: string; stop: () => void }>();

  const sourceOf = (it: GridPlate): Aspect => (it.native.has(shape) ? shape : '16:9');

  /** Starts showing the current theme and shape on `it` unless it shows them or is already getting them. */
  function want(it: GridPlate): void {
    const source = sourceOf(it);
    const key = `${token} ${source}`;
    if (shown.get(it) === key || jobs.get(it)?.key === key) return;
    jobs.get(it)?.stop();
    const stop = keepShowing(it.plate, it.data, source, seeds, {
      shown: () => {
        shown.set(it, key);
        jobs.delete(it);
      },
      wanted: () => near.has(it),
    });
    jobs.set(it, { key, stop });
  }

  function drop(it: GridPlate): void {
    jobs.get(it)?.stop();
    jobs.delete(it);
  }

  function place(it: GridPlate): void {
    const t = it.native.has(shape) ? 50 : focusPosition(shape, it.focus) * 100;
    it.plate.style.setProperty('--pos', cropAxis(shape) === 'x' ? `${t}% 0%` : `0% ${t}%`);
    const href = shape === home ? `/${it.slug}` : `/${it.slug}?shape=${aspectLabel(shape)}`;
    if (it.link.getAttribute('href') !== href) it.link.setAttribute('href', href);
  }

  function setShape(next: Aspect): void {
    shape = next;
    root.dataset.shape = next;
    for (const it of items.values()) place(it);
    for (const it of near) want(it);
  }

  // Rows are observed rather than plates: a plate inside a row that content-visibility skips never intersects.
  const io = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        const it = items.get(e.target);
        if (!it) continue;
        if (e.isIntersecting) {
          near.add(it);
          want(it);
        } else {
          near.delete(it);
          drop(it);
        }
      }
    },
    { rootMargin: '100% 0px' },
  );
  setShape(shape);
  for (const li of items.keys()) io.observe(li);

  // Only plates near the view are redrawn; the rest are stale until they come near.
  onThemeChange((s) => {
    seeds = s;
    token = tokenOf(s);
    for (const it of near) want(it);
  });

  return { setShape };
}
