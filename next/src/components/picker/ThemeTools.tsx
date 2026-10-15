'use client';
/**
 * The masthead's theme tools: the shared-theme line and the theme button that opens #picker.
 * Until hydration they show the default theme, as the server rendered them.
 */
import { useRef, useSyncExternalStore } from 'react';
import { dropShared, keepShared, useSharedDiffers } from '../../client/theme/use-choice';
import { useTheme } from '../../client/theme/use-theme';
import { DEFAULT_PRESET, presetLabel } from '../../lib/presets';
import { presetOf } from '../../lib/theme';
import { Chips } from '../Chips';
import { PICKER_ID } from './ids';

// `toggle` does not bubble, so listen in the capture phase.
function subscribeToggle(onChange: () => void): () => void {
  document.addEventListener('toggle', onChange, true);
  return () => document.removeEventListener('toggle', onChange, true);
}

const pickerOpen = () => document.getElementById(PICKER_ID)?.matches(':popover-open') ?? false;
const closed = () => false;

export function ThemeTools() {
  const theme = useTheme();
  const shared = useSharedDiffers();
  const open = useSyncExternalStore(subscribeToggle, pickerOpen, closed);
  const button = useRef<HTMLButtonElement>(null);
  const seeds = theme?.seeds ?? DEFAULT_PRESET;
  const name = theme ? (presetOf(theme.seeds) ?? 'custom') : DEFAULT_PRESET.name;

  return (
    <>
      <p className="shared" id="shared" hidden={!shared}>
        <span className="lead">You’re looking at a shared theme.</span>
        <button
          type="button"
          className="textbtn"
          data-action="keep-shared"
          onClick={() => {
            keepShared();
            button.current?.focus();
          }}
        >
          Keep it
        </button>
        <span className="sep">·</span>
        <button
          type="button"
          className="textbtn"
          data-action="drop-shared"
          onClick={() => {
            dropShared();
            button.current?.focus();
          }}
        >
          Back to yours
        </button>
      </p>
      <button
        ref={button}
        className="seeds"
        id="theme-button"
        type="button"
        popoverTarget={PICKER_ID}
        aria-expanded={open}
        aria-label={presetLabel({ ...seeds, name })}
      >
        <span className="name mono">{name}</span>
        <Chips colors={['var(--seed-bg)', 'var(--seed-fg)', 'var(--seed-accent)']} />
      </button>
    </>
  );
}
