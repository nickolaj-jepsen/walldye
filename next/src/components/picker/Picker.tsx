'use client';
/**
 * The theme popover the masthead's theme button opens: themes and families, the three colors with
 * their warnings, import from a terminal theme, and Copy link. Typed colors apply once typing
 * pauses. Dragging in a color picker repaints the site and every plate at once through the
 * `<html>` custom properties, and saves once the drag pauses.
 */
import {
  type CSSProperties,
  type ToggleEvent,
  useEffect,
  useEffectEvent,
  useLayoutEffect,
  useRef,
  useState,
} from 'react';
import { currentSeeds } from '../../client/theme/current';
import { endPreview, previewTheme } from '../../client/theme/preview';
import { chooseFamily, choosePreset, usePressed } from '../../client/theme/use-choice';
import { chooseTheme, useTheme } from '../../client/theme/use-theme';
import { seedsFromText } from '../../lib/import-theme';
import { DEFAULT_PRESET, FAMILIES, presetColors } from '../../lib/presets';
import {
  normalizeSeed,
  parseToken,
  SEED_PATTERN,
  SEEDS,
  type Seed,
  type Seeds,
} from '../../lib/theme';
import { Chips } from '../Chips';
import { CopyLink } from './CopyLink';
import { PICKER_ID } from './ids';
import { warningsFor } from './warnings';

/** How long typing must pause before a valid color applies. */
const DEBOUNCE_MS = 250;

const FIELDS: readonly { seed: Seed; label: string }[] = [
  { seed: 'bg', label: 'Background' },
  { seed: 'fg', label: 'Foreground' },
  { seed: 'accent', label: 'Accent' },
];

type Texts = Record<Seed, string>;
type Marks = Record<Seed, boolean>;

const textsOf = (s: Seeds): Texts => ({ bg: s.bg, fg: s.fg, accent: s.accent });

/** The typed colors as seeds, or null while any field holds no valid color. */
function seedsOf(t: Texts): Seeds | null {
  const bg = normalizeSeed(t.bg);
  const fg = normalizeSeed(t.fg);
  const accent = normalizeSeed(t.accent);
  return bg && fg && accent ? { bg, fg, accent } : null;
}

/** `:user-invalid`: the pattern fails and the visitor has left the field, so an empty one counts only then. */
function userInvalid(input: HTMLInputElement | undefined): boolean {
  try {
    return input?.matches(':user-invalid') ?? false;
  } catch {
    return false;
  }
}

export function Picker() {
  const theme = useTheme();
  const pressed = usePressed();
  const applied: Seeds = theme?.seeds ?? DEFAULT_PRESET;
  const [texts, setTexts] = useState<Texts>(() => textsOf(DEFAULT_PRESET));
  const [marks, setMarks] = useState<Marks>({ bg: false, fg: false, accent: false });
  const [importText, setImportText] = useState('');
  const [importFailed, setImportFailed] = useState(false);
  // Timers and native listeners read the fields through these, never through a stale render.
  const latest = useRef(texts);
  const pending = useRef(0);
  const inputs = useRef<Partial<Record<Seed, HTMLInputElement>>>({});
  const popover = useRef<HTMLDivElement>(null);

  function put(next: Texts) {
    latest.current = next;
    setTexts(next);
  }

  function cancelPending() {
    clearTimeout(pending.current);
    pending.current = 0;
  }

  /**
   * Fields back to `seeds`, the applied theme, dropping unapplied edits and any preview; the
   * focused field keeps its text unless `all`.
   */
  function fill(all: boolean, seeds: Seeds = currentSeeds()) {
    const next = { ...latest.current };
    for (const k of SEEDS) {
      if (all || document.activeElement !== inputs.current[k]) next[k] = seeds[k];
    }
    put(next);
    if (all) endPreview();
  }

  /**
   * Applies the fields when all three hold valid colors that differ from the applied theme; `final`
   * when the visitor left or submitted a field.
   */
  function commit(final: boolean) {
    cancelPending();
    const seeds = seedsOf(latest.current);
    if (!seeds) {
      endPreview();
      return;
    }
    const now = currentSeeds();
    if (SEEDS.some((k) => seeds[k] !== now[k])) chooseTheme(seeds);
    if (final) put(textsOf(seeds));
  }

  /** After the visitor typed, pasted or picked: shows `next` and schedules a commit. */
  function edited(next: Texts) {
    put(next);
    clearTimeout(pending.current);
    pending.current = window.setTimeout(() => commit(false), DEBOUNCE_MS);
  }

  function picked(k: Seed, value: string) {
    const next = { ...latest.current, [k]: value.toUpperCase() };
    const seeds = seedsOf(next);
    if (seeds) previewTheme(seeds);
    edited(next);
  }

  /** Puts `seeds` in the three fields, to apply like typed colors. */
  function fillFrom(seeds: Seeds) {
    setImportFailed(false);
    edited(textsOf(seeds));
  }

  /** Reads a theme from `text` into the fields, or says it holds none. */
  function importTheme(text: string) {
    const seeds = seedsFromText(text);
    if (seeds) {
      setImportText('');
      fillFrom(seeds);
    } else {
      setImportFailed(text.trim() !== '');
    }
  }

  function measure() {
    const next: Marks = {
      bg: userInvalid(inputs.current.bg),
      fg: userInvalid(inputs.current.fg),
      accent: userInvalid(inputs.current.accent),
    };
    setMarks((prev) => (SEEDS.every((k) => prev[k] === next[k]) ? prev : next));
  }

  // :user-invalid lives in the DOM, so read it back after every render; equal marks re-render nothing.
  useLayoutEffect(() => {
    measure();
  });

  // An edit waiting on its debounce keeps its fields when another theme is applied.
  const onApplied = useEffectEvent((seeds: Seeds) => {
    if (!pending.current) fill(false, seeds);
  });
  const token = theme?.token ?? null;
  useEffect(() => {
    const seeds = parseToken(token);
    if (seeds) onApplied(seeds);
  }, [token]);

  const onKey = useEffectEvent((e: KeyboardEvent) => {
    if (e.key === 'Escape' && popover.current?.matches(':popover-open')) {
      cancelPending();
      fill(true);
    }
  });
  useEffect(() => {
    const listener = (e: KeyboardEvent) => onKey(e);
    // Capture runs before the popover's own Escape handling closes it.
    document.addEventListener('keydown', listener, true);
    return () => document.removeEventListener('keydown', listener, true);
  }, []);

  function onToggle(e: ToggleEvent<HTMLDivElement>) {
    // `toggle` is queued, so typing can land before it; an edit waiting on its debounce is kept.
    if (e.newState === 'open') {
      if (!pending.current) fill(true);
      return;
    }
    if (pending.current) commit(false);
    cancelPending();
    fill(true);
  }

  const warn = warningsFor(texts);

  return (
    <div
      id={PICKER_ID}
      ref={popover}
      className="picker"
      popover="auto"
      role="dialog"
      aria-labelledby="picker-h"
      onToggle={onToggle}
    >
      <h2 id="picker-h" className="vh">
        Theme
      </h2>
      <div className="group">
        <h3 className="sc">Themes</h3>
        {/* A family's name follows the system scheme; its swatches fix one of its two themes. */}
        <ul className="presets">
          {FAMILIES.map((f) => (
            <li key={f.name}>
              {f.light ? (
                <>
                  <button
                    type="button"
                    className="family"
                    data-family={f.name}
                    aria-pressed={pressed.family === f.name}
                    onClick={() => {
                      cancelPending();
                      chooseFamily(f.name);
                      fill(true);
                    }}
                  >
                    <span className="name">{f.name}</span>
                    <span className="leader" />
                  </button>
                  {[f.dark, f.light].map((name) => (
                    <button
                      key={name}
                      type="button"
                      className="swatch"
                      data-preset={name}
                      aria-pressed={pressed.preset === name}
                      aria-label={name}
                      title={name}
                      onClick={() => {
                        cancelPending();
                        choosePreset(name);
                        fill(true);
                      }}
                    >
                      <Chips colors={presetColors(name)} />
                    </button>
                  ))}
                </>
              ) : (
                <button
                  type="button"
                  className="single"
                  data-preset={f.dark}
                  aria-pressed={pressed.preset === f.dark}
                  onClick={() => {
                    cancelPending();
                    choosePreset(f.dark);
                    fill(true);
                  }}
                >
                  <span className="entryname">
                    <span className="name">{f.name}</span>
                    <span className="leader" />
                  </span>
                  <Chips colors={presetColors(f.dark)} />
                </button>
              )}
            </li>
          ))}
        </ul>
      </div>
      <div className="group hair-t">
        <h3 className="sc">Colors</h3>
        {FIELDS.map(({ seed: k, label }) => {
          const typed = normalizeSeed(texts[k]);
          // The typed color while it is valid but not applied yet, else the applied seed.
          const shown = typed && typed !== applied[k] ? typed : null;
          let note: string | undefined;
          if (marks[k]) note = 'seed-msg';
          else if (k !== 'accent') note = warn.faint ? 'faint-msg' : undefined;
          else if (warn.nearBg) note = 'accent-bg-msg';
          else if (warn.nearFg) note = 'accent-fg-msg';
          return (
            <div key={k} className="hexfield">
              <label className="k" htmlFor={`seed-${k}`}>
                {label}
              </label>
              <span
                className="chip"
                style={{ '--c': shown ?? `var(--seed-${k})` } as CSSProperties}
              >
                <input
                  type="color"
                  value={(shown ?? applied[k]).toLowerCase()}
                  aria-label={`Pick ${label.toLowerCase()} color`}
                  onChange={(e) => picked(k, e.currentTarget.value)}
                />
              </span>
              <input
                id={`seed-${k}`}
                ref={(el) => {
                  inputs.current[k] = el ?? undefined;
                }}
                data-seed={k}
                value={texts[k]}
                required
                pattern={`\\s*${SEED_PATTERN}\\s*`}
                spellCheck={false}
                autoComplete="off"
                autoCapitalize="characters"
                aria-invalid={marks[k] || undefined}
                aria-describedby={note}
                onChange={(e) => edited({ ...latest.current, [k]: e.currentTarget.value })}
                onBlur={() => {
                  commit(true);
                  // WebKit sets :user-invalid a task after leaving the field.
                  setTimeout(measure);
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') commit(true);
                }}
                onPaste={(e) => {
                  const seeds = seedsFromText(e.clipboardData?.getData('text') ?? '');
                  if (!seeds) return;
                  e.preventDefault();
                  fillFrom(seeds);
                }}
              />
            </div>
          );
        })}
        <label className="importfield">
          <span className="k">Import</span>
          <input
            id="theme-import"
            value={importText}
            placeholder="paste a terminal theme"
            spellCheck={false}
            autoComplete="off"
            aria-describedby="import-msg"
            onChange={(e) => {
              setImportText(e.currentTarget.value);
              setImportFailed(false);
            }}
            // A pasted file is read whole: the field itself would keep only its first line.
            onPaste={(e) => {
              e.preventDefault();
              importTheme(e.clipboardData?.getData('text') ?? '');
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && e.currentTarget.value) importTheme(e.currentTarget.value);
            }}
            onBlur={(e) => {
              if (e.currentTarget.value) importTheme(e.currentTarget.value);
            }}
          />
        </label>
        <div className="msgs" aria-live="polite">
          <p id="seed-msg" className="msg err">
            Use a hex color, like <span className="mono">#CF6A4C</span>.
          </p>
          <p id="faint-msg" className="msg warn" hidden={!warn.faint}>
            The background and foreground are too close, so wallpapers will be hard to see.
          </p>
          <p id="accent-bg-msg" className="msg warn" hidden={!warn.nearBg}>
            The accent is too close to the background, so it will barely show in wallpapers.
          </p>
          <p id="accent-fg-msg" className="msg warn" hidden={!warn.nearFg}>
            The accent is too close to the foreground, so it will barely stand out in wallpapers.
          </p>
          <p id="import-msg" className="msg err" hidden={!importFailed}>
            No colors found in that text.
          </p>
        </div>
      </div>
      <p className="actions">
        <CopyLink />
      </p>
    </div>
  );
}
