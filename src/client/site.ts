/**
 * Every page: the header's theme button, the shared-theme line, the theme picker, the index's theme
 * row and "Copy link".
 * The theme boot has already applied the theme; this module keeps the controls in step with it,
 * saves the visitor's edits and counts their theme changes and copied links.
 */
import type { ThemeKind, ThemeVia } from '../lib/events';
import { seedsFromText } from '../lib/import-theme';
import { FAMILIES, NEAR_ACCENT, pairedFamily, presetLabel } from '../lib/presets';
import {
  contrast,
  distance,
  normalizeSeed,
  PRESETS,
  presetOf,
  SEEDS,
  type Seed,
  type Seeds,
  tokenOf,
} from '../lib/theme';
import { copyText, flash } from './clipboard';
import { must } from './dom';
import { track } from './events';
import { currentSeeds, onThemeChange } from './theme/current';
import {
  applyTheme,
  clearShared,
  ownChoice,
  ownTheme,
  savePair,
  saveTheme,
  sharedDiffers,
  sharedTheme,
} from './theme/store';

/** How long typing must pause before a valid color applies. */
const DEBOUNCE_MS = 250;
/** Raw bg/fg contrast under which the picker warns that wallpapers will be hard to see. */
const FAINT = 3;

const themeButton = must('#theme-button');
const themeName = must('[data-theme-name]', themeButton);
const sharedLine = must('#shared');
const picker = must('#picker');
// The picker's themes and, on the index, the row above the grid.
const presetButtons = [...document.querySelectorAll<HTMLButtonElement>('button[data-preset]')];
const familyButtons = [...document.querySelectorAll<HTMLButtonElement>('button[data-family]')];
const fields = Object.fromEntries(
  SEEDS.map((k) => [k, must<HTMLInputElement>(`#seed-${k}`)]),
) as Record<Seed, HTMLInputElement>;
const chips = Object.fromEntries(
  SEEDS.map((k) => [k, must('.chip', fields[k].closest('.hexfield') ?? picker)]),
) as Record<Seed, HTMLElement>;
// The native color picker inside each field's swatch.
const picks = Object.fromEntries(
  SEEDS.map((k) => [k, must<HTMLInputElement>('input[type=color]', chips[k])]),
) as Record<Seed, HTMLInputElement>;
const faintMsg = must('#faint-msg');
const accentFgMsg = must('#accent-fg-msg');
const accentBgMsg = must('#accent-bg-msg');
const importField = must<HTMLInputElement>('#theme-import');
const importMsg = must('#import-msg');

/** The debounced commit waiting to run, or 0. */
let pending = 0;
/** How the fields were last edited: typed or pasted, the native color picker, or imported. */
type Via = Extract<ThemeVia, 'hex' | 'wheel' | 'import'>;
let via: Via = 'hex';
/** How the custom theme committed since the picker opened was entered; counted once on close. */
let customVia: Via | null = null;

/** Counts a theme change; `name` is the preset or family, `custom` for anything else. */
function counted(kind: ThemeKind, name: string, place: ThemeVia): void {
  track({ event: 'theme', kind, name, via: place });
}

/** Where a theme button sits: the picker, or the index's color row. */
function placeOf(b: HTMLElement): ThemeVia {
  return b.closest('#picker') ? 'picker' : 'index';
}

/** The visitor's own choice by name: its family, its preset, or `custom`. */
function ownName(): string {
  const choice = ownChoice();
  if ('token' in choice) return Object.hasOwn(PRESETS, choice.token) ? choice.token : 'custom';
  const [dark, light] = choice.pair;
  return FAMILIES.find((f) => f.dark === dark && f.light === light)?.name ?? 'custom';
}

/** Counts a custom theme committed since the picker opened, once. */
function countCustom(): void {
  if (customVia) counted('custom', 'custom', customVia);
  customVia = null;
}

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
 * The fields' invalid marks (the pattern's `:user-invalid`, so an empty field counts only once the
 * visitor left it), the warnings when bg and fg are too close or the accent is too close to
 * either, and each swatch and color picker: the typed color while it is valid but not applied yet,
 * else the applied seed.
 */
function renderFields(): void {
  const bg = normalizeSeed(fields.bg.value);
  const fg = normalizeSeed(fields.fg.value);
  const accent = normalizeSeed(fields.accent.value);
  const faint = bg !== null && fg !== null && contrast(bg, fg) < FAINT;
  // One accent warning at a time; vanishing into the ground is the worse of the two.
  const nearBg = bg !== null && accent !== null && distance(accent, bg) < NEAR_ACCENT;
  const nearFg = !nearBg && fg !== null && accent !== null && distance(accent, fg) < NEAR_ACCENT;
  const applied = currentSeeds();
  for (const k of SEEDS) {
    const input = fields[k];
    const bad = input.matches(':user-invalid');
    if (bad) input.setAttribute('aria-invalid', 'true');
    else input.removeAttribute('aria-invalid');
    let note: string | null = null;
    if (bad) note = 'seed-msg';
    else if (k !== 'accent') note = faint ? 'faint-msg' : null;
    else note = nearBg ? 'accent-bg-msg' : nearFg ? 'accent-fg-msg' : null;
    if (note) input.setAttribute('aria-describedby', note);
    else input.removeAttribute('aria-describedby');
    const v = normalizeSeed(input.value);
    const shown = v && v !== applied[k] ? v : null;
    chips[k].style.setProperty('--c', shown ?? `var(--seed-${k})`);
    picks[k].value = (shown ?? applied[k]).toLowerCase();
  }
  faintMsg.hidden = !faint;
  accentBgMsg.hidden = !nearBg;
  accentFgMsg.hidden = !nearFg;
}

/** Fields back to the applied theme, dropping unapplied edits; the focused field keeps its text unless `all`. */
function fillFields(all: boolean): void {
  const seeds = currentSeeds();
  for (const k of SEEDS) {
    if (!all && document.activeElement === fields[k]) continue;
    fields[k].value = seeds[k];
  }
  renderFields();
}

/**
 * Applies the fields when all three hold valid colors that differ from the applied theme; `final`
 * when the visitor left or submitted a field.
 */
function commit(final: boolean): void {
  cancelPending();
  const values: Partial<Seeds> = {};
  for (const k of SEEDS) {
    const v = normalizeSeed(fields[k].value);
    if (v !== null) values[k] = v;
  }
  renderFields();
  const { bg, fg, accent } = values;
  if (!bg || !fg || !accent) return;
  const seeds = { bg, fg, accent };
  const applied = currentSeeds();
  if (SEEDS.some((k) => seeds[k] !== applied[k])) {
    choose(seeds);
    customVia = presetOf(seeds) === null ? via : null;
  }
  if (final) for (const k of SEEDS) fields[k].value = seeds[k];
}

/** After the visitor typed or pasted: renders the fields and schedules a commit. */
function edited(): void {
  renderFields();
  clearTimeout(pending);
  pending = window.setTimeout(() => commit(false), DEBOUNCE_MS);
}

/**
 * Header, picker and detail color list for the applied theme. The pressed theme is the visitor's
 * choice, a family or a fixed theme, unless a shared theme that differs from it is showing.
 */
function sync(seeds: Seeds): void {
  const name = presetOf(seeds) ?? 'custom';
  themeButton.setAttribute('aria-label', presetLabel({ name, ...seeds }));
  themeName.textContent = name;
  const differs = sharedDiffers();
  sharedLine.hidden = !differs;
  const choice = differs ? { token: tokenOf(seeds) } : ownChoice();
  for (const b of presetButtons) {
    b.setAttribute('aria-pressed', String('token' in choice && b.dataset.preset === choice.token));
  }
  for (const b of familyButtons) {
    const f = pairedFamily(b.dataset.family ?? '');
    const on = 'pair' in choice && choice.pair[0] === f?.dark && choice.pair[1] === f.light;
    b.setAttribute('aria-pressed', String(on));
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
    customVia = null;
    if (!pending) fillFields(true);
  } else {
    if (pending) commit(false);
    cancelPending();
    countCustom();
    fillFields(true);
  }
});
// Leaving with the picker open fires no toggle; an edit still on its debounce is neither saved nor counted.
addEventListener('pagehide', countCustom);
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
    customVia = null;
    counted('preset', name, placeOf(b));
  });
}

for (const b of familyButtons) {
  b.addEventListener('click', () => {
    const f = pairedFamily(b.dataset.family ?? '');
    if (!f?.light) return;
    cancelPending();
    savePair([f.dark, f.light]);
    applyTheme(ownTheme().seeds);
    fillFields(true);
    customVia = null;
    counted('family', f.name, placeOf(b));
  });
}

for (const k of SEEDS) {
  const input = fields[k];
  input.addEventListener('input', () => {
    via = 'hex';
    edited();
  });
  input.addEventListener('change', () => {
    commit(true);
    // WebKit sets :user-invalid a task after `change`.
    setTimeout(renderFields);
  });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') commit(true);
  });
  input.addEventListener('paste', (e) => {
    const seeds = seedsFromText(e.clipboardData?.getData('text') ?? '');
    if (!seeds) return;
    e.preventDefault();
    via = 'hex';
    fillFrom(seeds);
  });
  // Dragging in the native picker fires `input` continuously; the field's debounce paces it.
  picks[k].addEventListener('input', () => {
    input.value = picks[k].value.toUpperCase();
    via = 'wheel';
    edited();
  });
  picks[k].addEventListener('change', () => {
    input.value = picks[k].value.toUpperCase();
    via = 'wheel';
    commit(true);
  });
}

/** Puts `seeds` in the three fields, to apply like typed colors. */
function fillFrom(seeds: Seeds): void {
  importMsg.hidden = true;
  for (const k of SEEDS) fields[k].value = seeds[k];
  edited();
}

/** Reads a theme from `text` into the fields, or says it holds none. */
function importTheme(text: string): void {
  const seeds = seedsFromText(text);
  if (seeds) {
    importField.value = '';
    via = 'import';
    fillFrom(seeds);
  } else {
    importMsg.hidden = text.trim() === '';
  }
}

// A pasted file is read whole: the field itself would keep only its first line.
importField.addEventListener('paste', (e) => {
  e.preventDefault();
  importTheme(e.clipboardData?.getData('text') ?? '');
});
importField.addEventListener('change', () => importTheme(importField.value));
importField.addEventListener('input', () => {
  importMsg.hidden = true;
});

for (const b of document.querySelectorAll<HTMLButtonElement>('[data-action=copy-link]')) {
  b.addEventListener('click', async () => {
    if (!(await copyText(currentLink()))) return;
    flash(b, 'Link copied');
    track({ event: 'share' });
  });
}

must('[data-action=keep-shared]', sharedLine).addEventListener('click', () => {
  const shared = sharedTheme();
  if (shared) saveTheme(shared.seeds);
  sync(currentSeeds());
  themeButton.focus();
  if (shared) counted('keep', presetOf(shared.seeds) ?? 'custom', 'shared');
});

must('[data-action=drop-shared]', sharedLine).addEventListener('click', () => {
  clearShared();
  applyTheme(ownTheme().seeds);
  themeButton.focus();
  counted('drop', ownName(), 'shared');
});

onThemeChange(sync);
sync(currentSeeds());
