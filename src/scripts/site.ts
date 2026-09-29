/**
 * Every page: the header's theme button, the shared-theme line, the theme picker and "Copy link".
 * The theme boot has already applied the theme; this module keeps the controls in step with it and
 * saves the visitor's edits.
 */
import { presetLabel } from '../components/presets';
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
import {
  applyTheme,
  clearShared,
  ownTheme,
  saveTheme,
  sharedDiffers,
  sharedTheme,
} from '../lib/theme-store';
import { copyText, flash } from './clipboard';
import { currentSeeds, onThemeChange } from './current-theme';

/** How long typing must pause before a valid colour applies. */
const DEBOUNCE_MS = 250;
/** Raw bg/fg contrast under which the picker warns that wallpapers will be hard to see. */
const FAINT = 3;

const themeButton = document.getElementById('theme-button');
const themeName = themeButton?.querySelector<HTMLElement>('[data-theme-name]');
const sharedLine = document.getElementById('shared');
const picker = document.getElementById('picker');
const presetButtons = [
  ...document.querySelectorAll<HTMLButtonElement>('#picker .presets button[data-preset]'),
];
const fields = Object.fromEntries(
  SEEDS.map((k) => [k, document.getElementById(`seed-${k}`) as HTMLInputElement | null]),
) as Record<Seed, HTMLInputElement | null>;
const seedMsg = document.getElementById('seed-msg');
const faintMsg = document.getElementById('faint-msg');

let pending = 0;

/** Applies and saves `seeds` as the visitor's own theme, ending any shared one. */
function choose(seeds: Seeds): void {
  saveTheme(seeds);
  applyTheme(seeds);
}

function chipOf(input: HTMLInputElement): HTMLElement | null {
  const prev = input.previousElementSibling;
  return prev instanceof HTMLElement && prev.classList.contains('chip') ? prev : null;
}

function setDescribedBy(input: HTMLInputElement, id: string | null): void {
  if (id) input.setAttribute('aria-describedby', id);
  else input.removeAttribute('aria-describedby');
}

/** Error and warning state for the fields as they stand: the invalid ones, and a warning when bg and fg are too close. */
function syncMessages(): void {
  const bg = normaliseSeed(fields.bg?.value ?? '');
  const fg = normaliseSeed(fields.fg?.value ?? '');
  const faint = bg !== null && fg !== null && contrast(bg, fg) < FAINT;
  let invalid = false;
  for (const k of SEEDS) {
    const input = fields[k];
    if (!input) continue;
    const bad = input.getAttribute('aria-invalid') === 'true';
    invalid ||= bad;
    setDescribedBy(input, bad ? 'seed-msg' : faint && k !== 'accent' ? 'faint-msg' : null);
  }
  if (seedMsg) seedMsg.hidden = !invalid;
  if (faintMsg) faintMsg.hidden = !faint;
}

function markInvalid(input: HTMLInputElement, bad: boolean): void {
  if (bad) input.setAttribute('aria-invalid', 'true');
  else input.removeAttribute('aria-invalid');
}

/** Shows the typed colour on a field's swatch while it is valid but not applied yet. */
function previewChip(k: Seed, applied: Seeds): void {
  const input = fields[k];
  const chip = input && chipOf(input);
  if (!input || !chip) return;
  const v = normaliseSeed(input.value);
  if (v && v !== applied[k]) chip.style.setProperty('--c', v);
  else chip.style.setProperty('--c', `var(--seed-${k})`);
}

/** Fields back to `seeds`, dropping unapplied edits and their messages; the focused field keeps its text unless `all`. */
function fillFields(seeds: Seeds, all: boolean): void {
  for (const k of SEEDS) {
    const input = fields[k];
    if (!input) continue;
    if (all || document.activeElement !== input) {
      input.value = seeds[k];
      markInvalid(input, false);
    }
    previewChip(k, seeds);
  }
  syncMessages();
}

/**
 * Applies the fields when all three hold valid colours that differ from the applied theme. Marks
 * invalid fields; an empty field counts as invalid only when `final` (the visitor left or submitted it).
 */
function commit(final: boolean): void {
  clearTimeout(pending);
  pending = 0;
  const values: Partial<Seeds> = {};
  let ok = true;
  for (const k of SEEDS) {
    const input = fields[k];
    if (!input) return;
    const v = normaliseSeed(input.value);
    markInvalid(input, v === null && (final || input.value.trim() !== ''));
    if (v === null) ok = false;
    else values[k] = v;
  }
  syncMessages();
  if (!ok) return;
  const seeds = values as Seeds;
  const applied = currentSeeds();
  if (SEEDS.some((k) => seeds[k] !== applied[k])) choose(seeds);
  if (final) for (const k of SEEDS) if (fields[k]) fields[k]!.value = seeds[k];
}

function revert(): void {
  clearTimeout(pending);
  pending = 0;
  fillFields(currentSeeds(), true);
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
  if (themeButton) themeButton.setAttribute('aria-label', presetLabel({ name, ...seeds }));
  if (themeName) themeName.textContent = name;
  if (sharedLine) sharedLine.hidden = !sharedDiffers();
  for (const b of presetButtons)
    b.setAttribute('aria-pressed', String(b.dataset.preset === preset));
  for (const el of document.querySelectorAll<HTMLElement>('.seedlist [data-seed]')) {
    const k = el.dataset.seed as Seed;
    if (k in seeds) el.textContent = seeds[k];
  }
  if (!pending) fillFields(seeds, false);
}

function currentLink(): string {
  const url = new URL(location.href);
  url.hash = '';
  url.searchParams.delete('t');
  url.searchParams.set('t', tokenOf(currentSeeds()));
  return url.href;
}

if (picker) {
  picker.addEventListener('toggle', (e) => {
    const open = (e as ToggleEvent).newState === 'open';
    themeButton?.setAttribute('aria-expanded', String(open));
    // `toggle` is queued, so typing can land before it; an edit waiting on its debounce is kept.
    if (open) {
      if (!pending) fillFields(currentSeeds(), true);
    } else {
      if (pending) commit(false);
      revert();
    }
  });
  // Capture runs before the popover's own Escape handling closes it.
  document.addEventListener(
    'keydown',
    (e) => {
      if (e.key === 'Escape' && picker.matches(':popover-open')) revert();
    },
    true,
  );
}

for (const b of presetButtons) {
  b.addEventListener('click', () => {
    const name = b.dataset.preset ?? '';
    if (!Object.hasOwn(PRESETS, name)) return;
    clearTimeout(pending);
    pending = 0;
    choose({ ...PRESETS[name] });
    fillFields(currentSeeds(), true);
  });
}

for (const k of SEEDS) {
  const input = fields[k];
  if (!input) continue;
  input.addEventListener('input', () => {
    if (normaliseSeed(input.value)) markInvalid(input, false);
    previewChip(k, currentSeeds());
    syncMessages();
    clearTimeout(pending);
    pending = window.setTimeout(() => commit(false), DEBOUNCE_MS);
  });
  input.addEventListener('change', () => commit(true));
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') commit(true);
  });
  input.addEventListener('paste', (e) => {
    const seeds = pastedSeeds(e.clipboardData?.getData('text') ?? '');
    if (!seeds) return;
    e.preventDefault();
    for (const j of SEEDS) {
      if (!fields[j]) continue;
      fields[j]!.value = seeds[j];
      markInvalid(fields[j]!, false);
      previewChip(j, currentSeeds());
    }
    syncMessages();
    clearTimeout(pending);
    pending = window.setTimeout(() => commit(false), DEBOUNCE_MS);
  });
}

for (const b of document.querySelectorAll<HTMLButtonElement>('[data-action=copy-link]')) {
  b.addEventListener('click', async () => {
    if (await copyText(currentLink())) flash(b, 'Link copied');
  });
}

document.querySelector('[data-action=keep-shared]')?.addEventListener('click', () => {
  const shared = sharedTheme();
  if (shared) saveTheme(shared.seeds);
  sync(currentSeeds());
  themeButton?.focus();
});

document.querySelector('[data-action=drop-shared]')?.addEventListener('click', () => {
  clearShared();
  applyTheme(ownTheme().seeds);
  themeButton?.focus();
});

onThemeChange(sync);
sync(currentSeeds());
