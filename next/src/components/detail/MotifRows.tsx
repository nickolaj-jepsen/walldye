'use client';
/**
 * The motif's Across, Down and Scale ranges, the keyboard control for the handle on the plate. Each
 * has a button in a fixed slot: Center while the motif is off center on that axis, Reset once it has
 * moved. A button that hides under focus hands focus to its range.
 */
import { type MouseEvent, type RefObject, useLayoutEffect, useRef } from 'react';
import { CANVAS } from '../../lib/content';
import { centerMotif, clampPlacement, drawnPlacement, type Placement } from '../../lib/motif';
import styles from './Detail.module.css';
import { useDetail, useMotifPreview } from './detail-context';

type Refocus = { button: HTMLButtonElement; range: HTMLInputElement } | null;

export function MotifRows() {
  const d = useDetail();
  const { preview } = useMotifPreview();
  const across = useRef<HTMLInputElement>(null);
  const down = useRef<HTMLInputElement>(null);
  const scale = useRef<HTMLInputElement>(null);
  const refocus = useRef<Refocus>(null);

  // Runs after the render a button's click caused, once its `hidden` is current.
  useLayoutEffect(() => {
    const r = refocus.current;
    if (!r) return;
    refocus.current = null;
    if (r.button.hidden) r.range.focus();
  });

  const info = d.motif;
  if (!info) return null;
  const [w, h] = CANVAS[d.state.aspect];
  const p: Placement = preview ?? d.placement ?? drawnPlacement(info);
  const den = info.cell ?? 100;
  const moved = d.state.at !== null || d.state.scale !== null;

  /** Writes `next` as the range would offer it. */
  const place = (next: Placement) => {
    const c = clampPlacement(info, w, h, next);
    d.setMotif({ at: [c.x, c.y], scale: c.k });
  };

  /** Runs `act` for a click on a button, handing focus to `range` if the click hides the button. */
  const click =
    (range: RefObject<HTMLInputElement | null>, act: () => void) =>
    (e: MouseEvent<HTMLButtonElement>) => {
      const button = e.currentTarget;
      if (document.activeElement === button && range.current) {
        refocus.current = { button, range: range.current };
      }
      act();
    };

  const center = (axis: 'x' | 'y') => {
    const { x, y } = centerMotif(info, w, h, p, axis);
    d.setMotif({ at: [x, y] });
  };
  const centered = (axis: 'x' | 'y') => centerMotif(info, w, h, p, axis)[axis] === p[axis];

  return (
    <div id="motif-rows">
      <div className="row center">
        <span className="k">Across</span>
        <div className={styles.pair}>
          <input
            ref={across}
            className="range"
            id="place-x"
            type="range"
            min={0}
            max={w}
            step={1}
            value={Math.round(p.x)}
            aria-label="Across"
            onChange={(e) => place({ ...p, x: Number(e.currentTarget.value) })}
          />
          <button
            type="button"
            className="textbtn"
            aria-label="Center across"
            hidden={centered('x')}
            onClick={click(across, () => center('x'))}
          >
            Center
          </button>
        </div>
      </div>
      <div className="row center">
        <span className="k">Down</span>
        <div className={styles.pair}>
          <input
            ref={down}
            className="range"
            id="place-y"
            type="range"
            min={0}
            max={h}
            step={1}
            value={Math.round(p.y)}
            aria-label="Down"
            onChange={(e) => place({ ...p, y: Number(e.currentTarget.value) })}
          />
          <button
            type="button"
            className="textbtn"
            aria-label="Center down"
            hidden={centered('y')}
            onClick={click(down, () => center('y'))}
          >
            Center
          </button>
        </div>
      </div>
      <div className="row center">
        <span className="k">Scale</span>
        <div className={styles.pair}>
          <input
            ref={scale}
            className="range"
            id="place-k"
            type="range"
            min={Math.ceil(info.scale[0] * den - 1e-9)}
            max={Math.floor(info.scale[1] * den + 1e-9)}
            step={1}
            value={Math.round(p.k * den)}
            aria-label="Scale"
            aria-valuetext={`${Math.round(p.k * 100)}%`}
            onChange={(e) => place({ ...p, k: Number(e.currentTarget.value) / den })}
          />
          <button
            type="button"
            className="textbtn"
            hidden={!moved}
            onClick={click(scale, () => d.setMotif({ at: null, scale: null }))}
          >
            Reset
          </button>
        </div>
      </div>
    </div>
  );
}
