/**
 * The index page: facet filtering, search and sort with the state in the query string, live counts
 * and the results line (SPEC 6.4), and lazily recoloured plates (docs/design.md, Index).
 */
import { tokenOf, regimeOf, type Seeds } from '../lib/theme';
import { currentSeeds, onThemeChange } from './current-theme';
import { countFor, matches, ordered, parseQuery, serialiseQuery, type Filterable, type FilterState } from './filter';
import { RETRY_MS, showPlate, showTemplate, syncDarkNotes } from './plates';

interface Item extends Filterable {
  li: HTMLLIElement;
  plate: HTMLElement | null;
}

const form = document.getElementById('facets') as HTMLFormElement | null;
const grid = document.querySelector<HTMLUListElement>('.plates .grid');
const items: Item[] = [...(grid?.querySelectorAll<HTMLLIElement>(':scope > li') ?? [])].map((li) => ({
  li,
  slug: li.dataset.slug ?? '',
  title: li.dataset.title ?? '',
  added: li.dataset.added ?? '',
  facets: new Set((li.dataset.facets ?? '').split(' ').filter(Boolean)),
  search: li.dataset.search ?? '',
  plate: li.querySelector<HTMLElement>('.plate'),
}));

// ---- filters ----

if (form && grid) {
  const search = form.querySelector<HTMLInputElement>('#q')!;
  const boxes = [...form.querySelectorAll<HTMLInputElement>('input[type=checkbox]')];
  const sorts = [...form.querySelectorAll<HTMLInputElement>('input[name=sort]')];
  const status = document.getElementById('result-count');
  const clear = document.querySelector<HTMLElement>('.results-line .clear');
  const empty = document.querySelector<HTMLElement>('.plates .empty');
  const summary = document.querySelector<HTMLElement>('.filter > summary .state');
  const details = document.querySelector<HTMLDetailsElement>('details.filter');
  const order = boxes.map((b) => [b.name, b.value] as const);
  const total = items.length;
  const noun = total === 1 ? 'wallpaper' : 'wallpapers';

  const read = (): FilterState => {
    const facets = new Map<string, Set<string>>();
    for (const b of boxes) {
      if (!b.checked) continue;
      if (!facets.has(b.name)) facets.set(b.name, new Set());
      facets.get(b.name)!.add(b.value);
    }
    return { q: search.value, sort: sorts.find((r) => r.checked)?.value === 'title' ? 'title' : 'newest', facets };
  };

  const write = (s: FilterState) => {
    search.value = s.q;
    for (const r of sorts) r.checked = r.value === s.sort;
    for (const b of boxes) b.checked = s.facets.get(b.name)?.has(b.value) ?? false;
  };

  const apply = () => {
    const s = read();
    let shown = 0;
    for (const it of items) {
      const ok = matches(it, s);
      it.li.hidden = !ok;
      if (ok) shown++;
    }
    for (const b of boxes) {
      const n = countFor(items, s, b.name, b.value);
      const count = b.closest('label')?.querySelector('.count');
      if (count && count.textContent !== String(n)) count.textContent = String(n);
      b.disabled = n === 0 && !b.checked;
    }
    const text = shown === total ? `${total} ${noun}` : `${shown} of ${total} ${noun}`;
    // Rewriting an unchanged live region can re-announce it.
    if (status && status.textContent !== text) status.textContent = text;
    if (empty) empty.hidden = shown > 0;
    const needle = s.q.trim();
    const checked = boxes.filter((b) => b.checked);
    if (clear) clear.hidden = checked.length === 0 && needle === '';
    if (summary) {
      const terms = checked.map((b) => b.closest('label')?.querySelector('.term')?.textContent ?? b.value);
      if (needle) terms.unshift(`“${needle}”`);
      summary.textContent = terms.join(', ');
    }

    const sorted = ordered(items, s.sort);
    if (sorted.some((it, i) => grid.children[i] !== it.li)) grid.append(...sorted.map((it) => it.li));

    const url = new URL(location.href);
    url.search = serialiseQuery(s, order);
    if (url.href !== location.href) history.replaceState(history.state, '', url.href);
  };

  write(parseQuery(new URLSearchParams(location.search), (facet, value) => boxes.some((b) => b.name === facet && b.value === value)));
  apply();
  // The count only becomes a live region once it matches the address, so a filtered load is not announced.
  status?.setAttribute('role', 'status');

  form.addEventListener('submit', (e) => e.preventDefault());
  form.addEventListener('input', apply);
  form.addEventListener('change', apply);
  // `reset` fires before the controls are reset.
  form.addEventListener('reset', () => setTimeout(apply));

  if (details) {
    const wide = matchMedia('(min-width: 60.0625rem)');
    wide.addEventListener('change', () => {
      details.open = wide.matches;
    });
  }
}

// ---- plates ----

let seeds: Seeds = currentSeeds();
let token = tokenOf(seeds);
/** Plates within one viewport of the visible area. */
const near = new Set<HTMLElement>();
/** The theme token each plate shows or is being given. */
const shown = new WeakMap<HTMLElement, string>();
const todo = new Set<HTMLElement>();
let running = 0;
/** Failed loads per plate since its last success; each failure is retried after RETRY_MS[n]. */
const failures = new WeakMap<HTMLElement, number>();

function nextPlate(): HTMLElement {
  // Plates in view first, then the ones closest to it.
  let best: HTMLElement | null = null;
  let gap = Infinity;
  const vh = innerHeight;
  for (const p of todo) {
    const r = p.getBoundingClientRect();
    const d = r.bottom < 0 ? -r.bottom : r.top > vh ? r.top - vh : 0;
    if (d < gap) [best, gap] = [p, d];
  }
  return best ?? todo.values().next().value!;
}

function pump(): void {
  while (running < 6 && todo.size) {
    const plate = nextPlate();
    todo.delete(plate);
    if (!near.has(plate) || shown.get(plate) === token) continue;
    const t = token;
    shown.set(plate, t);
    running++;
    showPlate(plate, '16:9', seeds)
      .then(
        () => failures.delete(plate),
        () => {
          if (shown.get(plate) !== t) return;
          shown.delete(plate);
          // An empty box would say nothing: stand in with the untouched template and its alt text.
          if (!plate.querySelector(':scope > img')) showTemplate(plate, '16:9', seeds).catch(() => {});
          const n = failures.get(plate) ?? 0;
          failures.set(plate, n + 1);
          if (n < RETRY_MS.length) setTimeout(() => retry(plate), RETRY_MS[n]);
        },
      )
      .finally(() => {
        running--;
        pump();
      });
  }
}

function retry(plate: HTMLElement): void {
  if (!near.has(plate) || shown.get(plate) === token) return;
  todo.add(plate);
  pump();
}

addEventListener('online', () => {
  for (const p of near) {
    failures.delete(p);
    retry(p);
  }
});

// Rows are observed rather than plates: a plate inside a row that content-visibility skips never intersects.
const plateOf = new Map<Element, HTMLElement>();
const io = new IntersectionObserver(
  (entries) => {
    for (const e of entries) {
      const plate = plateOf.get(e.target);
      if (!plate) continue;
      if (e.isIntersecting) {
        near.add(plate);
        if (shown.get(plate) !== token) todo.add(plate);
      } else {
        near.delete(plate);
        todo.delete(plate);
      }
    }
    pump();
  },
  { rootMargin: '100% 0px' },
);

syncDarkNotes(regimeOf(seeds) === 'light');
for (const it of items) {
  if (!it.plate) continue;
  plateOf.set(it.li, it.plate);
  io.observe(it.li);
}

// Only plates near the view are re-templated; the rest are stale until they come near.
onThemeChange((s) => {
  seeds = s;
  token = tokenOf(s);
  syncDarkNotes(regimeOf(s) === 'light');
  todo.clear();
  for (const p of near) todo.add(p);
  pump();
});
