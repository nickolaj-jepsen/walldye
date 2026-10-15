'use client';
/**
 * The index's Colors row: one button per family, showing its theme for the system scheme (site.css
 * picks the set), and "Your own", which opens the picker. The pressed button is the visitor's own
 * choice, unless a shared theme that differs from it is showing; before hydration it is the default
 * family.
 */
import { chooseFamily, choosePreset, usePressed } from '../../client/theme/use-choice';
import { FAMILIES, presetColors } from '../../lib/presets';
import { Chips } from '../Chips';
import { PICKER_ID } from '../picker/ids';

export function ThemeRow() {
  const pressed = usePressed();
  return (
    // biome-ignore lint/a11y/useSemanticElements: a fieldset's legend and box would break the row's flex layout in site.css
    <div className="themes" role="group" aria-labelledby="themes-h">
      <h2 id="themes-h" className="sc">
        Colors
      </h2>
      {FAMILIES.map((f) => (
        <button
          key={f.name}
          type="button"
          aria-pressed={f.light ? pressed.family === f.name : pressed.preset === f.dark}
          aria-label={f.name}
          title={f.name}
          onClick={() => (f.light ? chooseFamily(f.name) : choosePreset(f.dark))}
        >
          {f.light ? (
            <>
              <Chips colors={presetColors(f.dark)} className="for-dark" />
              <Chips colors={presetColors(f.light)} className="for-light" />
            </>
          ) : (
            <Chips colors={presetColors(f.dark)} />
          )}
        </button>
      ))}
      <button type="button" className="textbtn" popoverTarget={PICKER_ID}>
        Your own
      </button>
    </div>
  );
}
