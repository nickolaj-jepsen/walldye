/**
 * The index page: facet filtering, search, sort and shape with the state in the query string, live
 * counts and the results line, and the plate grid (grid.ts).
 */
import { aspectLabel, isSortOrder, type SortOrder } from '../../lib/content';
import { formParams, must, replaceAddress } from '../dom';
import { plateGrid } from '../grid';
import { deviceAspect, WIDE_QUERY } from '../screen';
import {
  countFor,
  type Filterable,
  type FilterDefaults,
  filterQuery,
  filterState,
  matches,
  ordered,
} from './filter';

interface Item extends Filterable {
  li: HTMLLIElement;
}

const form = must<HTMLFormElement>('#facets');
const plates = must('section.plates');
const grid = must<HTMLUListElement>('.grid', plates);
const items: Item[] = [...grid.querySelectorAll<HTMLLIElement>(':scope > li')].map((li) => ({
  li,
  slug: li.dataset.slug ?? '',
  title: li.dataset.title ?? '',
  added: li.dataset.added ?? '',
  views: Number(li.dataset.views ?? 0),
  recent: Number(li.dataset.recent ?? 0),
  featured: li.dataset.featured === undefined ? undefined : Number(li.dataset.featured),
  facets: new Set((li.dataset.facets ?? '').split(' ').filter(Boolean)),
  search: li.dataset.search ?? '',
}));

// ---- filters ----

const search = must<HTMLInputElement>('#q', form);
const boxes = [...form.querySelectorAll<HTMLInputElement>('input[type=checkbox]')];
const sorts = [...form.querySelectorAll<HTMLInputElement>('input[name=sort]')];
const shapes = [...form.querySelectorAll<HTMLInputElement>('input[name=shape]')];
const status = must('#result-count');
const clear = must('.results-line .clear');
const empty = must('.plates .empty');
const summary = must('.filter > summary .state');
const details = must<HTMLDetailsElement>('details.filter');
const showResults = must<HTMLButtonElement>('#show-results', details);
const noun = items.length === 1 ? 'wallpaper' : 'wallpapers';
// The server checks the build's first order.
const firstSort = sorts.find((r) => r.defaultChecked)?.value;
const defaults: FilterDefaults = {
  sort: isSortOrder(firstSort) ? firstSort : ('newest' satisfies SortOrder),
  shape: deviceAspect(),
};
// So the form's reset comes back to the device's shape.
for (const r of shapes) r.defaultChecked = r.value === aspectLabel(defaults.shape);

/** Sets the controls from `params`, ignoring values that have no box or radio. */
function fill(params: URLSearchParams): void {
  const s = filterState(params, defaults);
  search.value = s.q;
  for (const r of sorts) r.checked = r.value === s.sort;
  if (!sorts.some((r) => r.checked)) for (const r of sorts) r.checked = r.value === defaults.sort;
  for (const r of shapes) r.checked = r.value === aspectLabel(s.shape);
  for (const b of boxes) b.checked = params.getAll(b.name).includes(b.value);
}

function apply(): void {
  const params = formParams(form);
  const s = filterState(params, defaults);
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
  showResults.textContent = `Show ${shown} ${shown === 1 ? 'wallpaper' : 'wallpapers'}`;
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

  view.setShape(s.shape);

  const url = new URL(location.href);
  url.search = filterQuery(params, defaults);
  replaceAddress(url);
}

fill(new URLSearchParams(location.search));
const view = plateGrid(plates, filterState(formParams(form), defaults).shape);
apply();
// The count only becomes a live region once it matches the address, so a filtered load is not announced.
status.setAttribute('role', 'status');

form.addEventListener('submit', (e) => e.preventDefault());
form.addEventListener('input', apply);
form.addEventListener('change', apply);
// `reset` fires before the controls are reset. "clear" clears the filters; the shape is kept.
form.addEventListener('reset', () => {
  const shape = shapes.find((r) => r.checked);
  setTimeout(() => {
    if (shape) shape.checked = true;
    apply();
  });
});

// Phones: close the filter and bring its summary, the color row and the grid into view.
showResults.addEventListener('click', () => {
  details.open = false;
  const toggle = must('summary', details);
  toggle.focus({ preventScroll: true });
  toggle.scrollIntoView({ block: 'start' });
});

const wide = matchMedia(WIDE_QUERY);
wide.addEventListener('change', () => {
  details.open = wide.matches;
});
