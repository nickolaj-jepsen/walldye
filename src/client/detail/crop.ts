/** The detail page's crop window: framing a shape's crop and moving it by dragging. */
import { cropAxis, cropSpan, type ExportShape } from '../../lib/shape';

/** Frames `shape`'s crop with `win`, a `.crop` inside a plate showing the 16:9 picture; hidden for a native shape. */
export function placeCrop(win: HTMLElement, shape: ExportShape): void {
  win.hidden = shape.native;
  if (shape.native) return;
  const span = cropSpan(shape.aspect);
  const offset = shape.t * (1 - span);
  const axis = cropAxis(shape.aspect);
  win.dataset.axis = axis;
  // Heights are fractions of the picture's (site.css .plate::after), not the plate's, which ends in a 0-7px rounding strip.
  const tall = (f: number) => `calc(${f} * 100cqw / var(--ratio))`;
  Object.assign(
    win.style,
    axis === 'x'
      ? { left: `${offset * 100}%`, width: `${span * 100}%`, top: '0', height: tall(1) }
      : { left: '0', width: '100%', top: tall(offset), height: tall(span) },
  );
}

/**
 * Follows the drag `e` starts on `el`, calling `move` with the crop position: `from` changed by
 * 1 / `travel` per pixel moved along the crop axis of `aspect`, against the pointer when
 * `reverse`, clamped to 0..1 and rounded to 0.001.
 */
export function dragCrop(
  el: HTMLElement,
  e: PointerEvent,
  aspect: string,
  from: number,
  travel: number,
  move: (t: number) => void,
  reverse = false,
): void {
  const x = cropAxis(aspect) === 'x';
  const start = x ? e.clientX : e.clientY;
  el.setPointerCapture(e.pointerId);
  const onMove = (ev: PointerEvent) => {
    const d = ((x ? ev.clientX : ev.clientY) - start) * (reverse ? -1 : 1);
    const next = Math.min(1, Math.max(0, from + (travel > 0 ? d / travel : 0)));
    move(Math.round(next * 1000) / 1000);
  };
  const end = () => {
    el.removeEventListener('pointermove', onMove);
    el.removeEventListener('pointerup', end);
    el.removeEventListener('pointercancel', end);
  };
  el.addEventListener('pointermove', onMove);
  el.addEventListener('pointerup', end);
  el.addEventListener('pointercancel', end);
}
