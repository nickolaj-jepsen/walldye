/**
 * Every page: the header's theme button, the shared-theme line, the theme picker and "Copy link".
 * The theme boot has already applied the theme; this module keeps the controls in step with it and
 * saves the visitor's edits.
 */
import { presetLabel } from '../lib/presets';
import {
  contrast,
  normaliseSeed,
  PRESETS,
  parseToken,
  presetOf,
  SEEDS,
  type Seed,
  type Seeds,
  tokenOf,
} from '../lib/theme';
import { copyText, flash } from './clipboard';
import { must } from './dom';
import { currentSeeds, onThemeChange } from './theme/current';
import {
  applyTheme,
  clearShared,
  ownTheme,
  saveTheme,
  sharedDiffers,
  sharedTheme,
} from './theme/store';

/** How long typing must pause before a valid colour applies. */
const DEBOUNCE_MS = 250;
/** Raw bg/fg contrast under which the picker warns that wallpapers will be hard to see. */
const FAINT = 3;

const themeButton = must('#theme-button');
const themeName = must('[data-theme-name]', themeButton);
const sharedLine = must('#shared');
const picker = must('#picker');
const presetButtons = [
  ...picker.querySelectorAll<HTMLButtonElement>('.presets button[data-preset]'),
];
const fields = Object.fromEntries(
  SEEDS.map((k) => [k, must<HTMLInputElement>(`#seed-${k}`)]),
) as Record<Seed, HTMLInputElement>;
const chips = Object.fromEntries(
  SEEDS.map((k) => [k, must('.chip', fields[k].closest('.hexfield') ?? picker)]),
) as Record<Seed, HTMLElement>;
const seedMsg = must('#seed-msg');
const faintMsg = must('#faint-msg');

/** The debounced commit waiting to run, or 0. */
let pending = 0;
/** Fields marked invalid; an empty field counts only once the visitor left or submitted it. */
const invalid = new Set<Seed>();

function cancelPending(): void {
  clearTimeout(pending);
  pending = 0;
}

/** Applies and saves `seeds` as the visitor's own theme, ending any shared one. */
function choose(seeds: Seeds): void {
  saveTheme(seeds);
  applyTheme(seeds);
}

/**
 * The fields' invalid marks, the warning when bg and fg are too close, and each swatch: the typed
 * colour while it is valid but not applied yet, else the applied seed.
 */
function renderFields(): void {
  const bg = normaliseSeed(fields.bg.value);
  const fg = normaliseSeed(fields.fg.value);
  const faint = bg !== null && fg !== null && contrast(bg, fg) < FAINT;
  const applied = currentSeeds();
  for (const k of SEEDS) {
    const input = fields[k];
    const bad = invalid.has(k);
    if (bad) input.setAttribute('aria-invalid', 'true');
    else input.removeAttribute('aria-invalid');
    const note = bad ? 'seed-msg' : faint && k !== 'accent' ? 'faint-msg' : null;
    if (note) input.setAttribute('aria-describedby', note);
    else input.removeAttribute('aria-describedby');
    const v = normaliseSeed(input.value);
    chips[k].style.setProperty('--c', v && v !== applied[k] ? v : `var(--seed-${k})`);
  }
  seedMsg.hidden = invalid.size === 0;
  faintMsg.hidden = !faint;
}

/** Fields back to the applied theme, dropping unapplied edits; the focused field keeps its text unless `all`. */
function fillFields(all: boolean): void {
  const seeds = currentSeeds();
  for (const k of SEEDS) {
    if (!all && document.activeElement === fields[k]) continue;
    fields[k].value = seeds[k];
    invalid.delete(k);
  }
  renderFields();
}

/**
 * Applies the fields when all three hold valid colours that differ from the applied theme, and marks
 * the invalid ones; `final` when the visitor left or submitted a field.
 */
function commit(final: boolean): void {
  cancelPending();
  const values: Partial<Seeds> = {};
  for (const k of SEEDS) {
    const v = normaliseSeed(fields[k].value);
    if (v !== null) values[k] = v;
    if (v === null && (final || fields[k].value.trim() !== '')) invalid.add(k);
    else invalid.delete(k);
  }
  renderFields();
  const { bg, fg, accent } = values;
  if (!bg || !fg || !accent) return;
  const seeds = { bg, fg, accent };
  const applied = currentSeeds();
  if (SEEDS.some((k) => seeds[k] !== applied[k])) choose(seeds);
  if (final) for (const k of SEEDS) fields[k].value = seeds[k];
}

/** After the visitor typed or pasted: clears the marks the edit fixed and schedules a commit. */
function edited(): void {
  for (const k of SEEDS) if (normaliseSeed(fields[k].value)) invalid.delete(k);
  renderFields();
  clearTimeout(pending);
  pending = window.setTimeout(() => commit(false), DEBOUNCE_MS);
}

/** Three colours from pasted text: a theme token, or three hex colours separated by commas, spaces or dashes. */
function pastedSeeds(text: string): Seeds | null {
  const t = text.trim();
  const token = parseToken(t);
  if (token) return token;
  const parts = t.split(/[\s,-]+/).filter(Boolean);
  if (parts.length !== 3) return null;
  const [bg, fg, accent] = parts.map(normaliseSeed);
  return bg && fg && accent ? { bg, fg, accent } : null;
}

/** Header, picker and detail colour list for the applied theme. */
function sync(seeds: Seeds): void {
  const preset = presetOf(seeds);
  const name = preset ?? 'custom';
  themeButton.setAttribute('aria-label', presetLabel({ name, ...seeds }));
  themeName.textContent = name;
  sharedLine.hidden = !sharedDiffers();
  for (const b of presetButtons) {
    b.setAttribute('aria-pressed', String(b.dataset.preset === preset));
  }
  for (const el of document.querySelectorAll<HTMLElement>('.seedlist [data-seed]')) {
    const k = el.dataset.seed;
    if (k === 'bg' || k === 'fg' || k === 'accent') el.textContent = seeds[k];
  }
  if (!pending) fillFields(false);
}

function currentLink(): string {
  const url = new URL(location.href);
  url.hash = '';
  url.searchParams.set('t', tokenOf(currentSeeds()));
  return url.href;
}

picker.addEventListener('toggle', (e) => {
  const open = (e as ToggleEvent).newState === 'open';
  themeButton.setAttribute('aria-expanded', String(open));
  // `toggle` is queued, so typing can land before it; an edit waiting on its debounce is kept.
  if (open) {
    if (!pending) fillFields(true);
  } else {
    if (pending) commit(false);
    cancelPending();
    fillFields(true);
  }
});
// Capture runs before the popover's own Escape handling closes it.
document.addEventListener(
  'keydown',
  (e) => {
    if (e.key === 'Escape' && picker.matches(':popover-open')) {
      cancelPending();
      fillFields(true);
    }
  },
  true,
);

for (const b of presetButtons) {
  b.addEventListener('click', () => {
    const name = b.dataset.preset ?? '';
    if (!Object.hasOwn(PRESETS, name)) return;
    cancelPending();
    choose({ ...PRESETS[name] });
    fillFields(true);
  });
}

for (const k of SEEDS) {
  const input = fields[k];
  input.addEventListener('input', edited);
  input.addEventListener('change', () => commit(true));
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') commit(true);
  });
  input.addEventListener('paste', (e) => {
    const seeds = pastedSeeds(e.clipboardData?.getData('text') ?? '');
    if (!seeds) return;
    e.preventDefault();
    for (const j of SEEDS) fields[j].value = seeds[j];
    edited();
  });
}

for (const b of document.querySelectorAll<HTMLButtonElement>('[data-action=copy-link]')) {
  b.addEventListener('click', async () => {
    if (await copyText(currentLink())) flash(b, 'Link copied');
  });
}

must('[data-action=keep-shared]', sharedLine).addEventListener('click', () => {
  const shared = sharedTheme();
  if (shared) saveTheme(shared.seeds);
  sync(currentSeeds());
  themeButton.focus();
});

must('[data-action=drop-shared]', sharedLine).addEventListener('click', () => {
  clearShared();
  applyTheme(ownTheme().seeds);
  themeButton.focus();
});

onThemeChange(sync);
sync(currentSeeds());
