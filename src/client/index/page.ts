/**
 * The index page: facet filtering, search and sort with the state in the query string, live counts
 * and the results line, and lazily recoloured plates.
 */
import { type Seeds, tokenOf } from '../../lib/theme';
import { formParams, must, replaceAddress } from '../dom';
import { keepShowing, type PlateData, plateData } from '../plates';
import { currentSeeds, onThemeChange } from '../theme/current';
import { countFor, type Filterable, filterQuery, filterState, matches, ordered } from './filter';

interface Item extends Filterable {
  li: HTMLLIElement;
  plate: HTMLElement;
  data: PlateData;
}

const form = must<HTMLFormElement>('#facets');
const grid = must<HTMLUListElement>('.plates .grid');
const items: Item[] = [...grid.querySelectorAll<HTMLLIElement>(':scope > li')].map((li) => {
  const plate = must('.plate', li);
  return {
    li,
    slug: li.dataset.slug ?? '',
    title: li.dataset.title ?? '',
    added: li.dataset.added ?? '',
    views: Number(li.dataset.views ?? 0),
    recent: Number(li.dataset.recent ?? 0),
    facets: new Set((li.dataset.facets ?? '').split(' ').filter(Boolean)),
    search: li.dataset.search ?? '',
    plate,
    data: plateData(plate),
  };
});

// ---- filters ----

const search = must<HTMLInputElement>('#q', form);
const boxes = [...form.querySelectorAll<HTMLInputElement>('input[type=checkbox]')];
const sorts = [...form.querySelectorAll<HTMLInputElement>('input[name=sort]')];
const status = must('#result-count');
const clear = must('.results-line .clear');
const empty = must('.plates .empty');
const summary = must('.filter > summary .state');
const details = must<HTMLDetailsElement>('details.filter');
const noun = items.length === 1 ? 'wallpaper' : 'wallpapers';

/** Sets the controls from `params`, ignoring values that have no box or radio. */
function fill(params: URLSearchParams): void {
  search.value = params.get('q') ?? '';
  const sort = params.get('sort') ?? 'newest';
  const known = sorts.some((r) => r.value === sort);
  for (const r of sorts) r.checked = r.value === (known ? sort : 'newest');
  for (const b of boxes) b.checked = params.getAll(b.name).includes(b.value);
}

function apply(): void {
  const params = formParams(form);
  const s = filterState(params);
  let shown = 0;
  for (const it of items) {
    const ok = matches(it, s);
    it.li.hidden = !ok;
    if (ok) shown++;
  }
  for (const b of boxes) {
    const n = String(countFor(items, s, b.name, b.value));
    const count = b.closest('label')?.querySelector('.count');
    if (count && count.textContent !== n) count.textContent = n;
    b.disabled = n === '0' && !b.checked;
  }
  const total = items.length;
  const text = shown === total ? `${total} ${noun}` : `${shown} of ${total} ${noun}`;
  // Rewriting an unchanged live region can re-announce it.
  if (status.textContent !== text) status.textContent = text;
  empty.hidden = shown > 0;
  const needle = s.q.trim();
  const checked = boxes.filter((b) => b.checked);
  clear.hidden = checked.length === 0 && needle === '';
  const terms = checked.map(
    (b) => b.closest('label')?.querySelector('.term')?.textContent ?? b.value,
  );
  if (needle) terms.unshift(`“${needle}”`);
  summary.textContent = terms.join(', ');

  const sorted = ordered(items, s.sort);
  if (sorted.some((it, i) => grid.children[i] !== it.li)) grid.append(...sorted.map((it) => it.li));

  const url = new URL(location.href);
  url.search = filterQuery(params);
  replaceAddress(url);
}

fill(new URLSearchParams(location.search));
apply();
// The count only becomes a live region once it matches the address, so a filtered load is not announced.
status.setAttribute('role', 'status');

form.addEventListener('submit', (e) => e.preventDefault());
form.addEventListener('input', apply);
form.addEventListener('change', apply);
// `reset` fires before the controls are reset.
form.addEventListener('reset', () => setTimeout(apply));

const wide = matchMedia('(min-width: 60.0625rem)');
wide.addEventListener('change', () => {
  details.open = wide.matches;
});

// ---- plates ----

let seeds: Seeds = currentSeeds();
let token = tokenOf(seeds);
/** Items within one viewport of the visible area. */
const near = new Set<Item>();
/** The theme token each plate shows. */
const shown = new WeakMap<Item, string>();
/** The load under way for a plate, and the token it is for. */
const jobs = new Map<Item, { token: string; stop: () => void }>();

/** Starts showing the current theme on `it` unless it shows it or is already getting it. */
function want(it: Item): void {
  if (shown.get(it) === token || jobs.get(it)?.token === token) return;
  jobs.get(it)?.stop();
  const t = token;
  const stop = keepShowing(it.plate, it.data, '16:9', seeds, {
    shown: () => {
      shown.set(it, t);
      jobs.delete(it);
    },
    wanted: () => near.has(it),
  });
  jobs.set(it, { token: t, stop });
}

function drop(it: Item): void {
  jobs.get(it)?.stop();
  jobs.delete(it);
}

// Rows are observed rather than plates: a plate inside a row that content-visibility skips never intersects.
const itemOf = new Map<Element, Item>(items.map((it) => [it.li, it]));
const io = new IntersectionObserver(
  (entries) => {
    for (const e of entries) {
      const it = itemOf.get(e.target);
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
for (const it of items) io.observe(it.li);

// Only plates near the view are re-templated; the rest are stale until they come near.
onThemeChange((s) => {
  seeds = s;
  token = tokenOf(s);
  for (const it of near) want(it);
});
