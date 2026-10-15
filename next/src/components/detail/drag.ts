/** Pointer drags on the detail plate: the crop window and the motif's handle. */
import { cropAxis } from '../../lib/shape';

/**
 * Follows the drag `e` starts on `el`, calling `move` with the crop position: `from` changed by
 * 1 / `travel` per pixel moved along the crop axis of `aspect`, against the pointer when `reverse`,
 * clamped to 0..1 and rounded to 0.001.
 */
export function dragCrop(
  el: Element,
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
  const onMove = (ev: Event) => {
    const p = ev as PointerEvent;
    if (p.pointerId !== e.pointerId) return;
    const d = ((x ? p.clientX : p.clientY) - start) * (reverse ? -1 : 1);
    const next = Math.min(1, Math.max(0, from + (travel > 0 ? d / travel : 0)));
    move(Math.round(next * 1000) / 1000);
  };
  const end = (ev: Event) => {
    if ((ev as PointerEvent).pointerId !== e.pointerId) return;
    el.removeEventListener('pointermove', onMove);
    el.removeEventListener('pointerup', end);
    el.removeEventListener('pointercancel', end);
  };
  el.addEventListener('pointermove', onMove);
  el.addEventListener('pointerup', end);
  el.addEventListener('pointercancel', end);
}

/**
 * Follows the drag `e` starts on `el`, calling `move` with how far that pointer has gone, in canvas
 * units at `units` per pixel, then `done` when it ends. Returns a function that drops the drag
 * without calling `done`.
 */
export function dragMotif(
  el: Element,
  e: PointerEvent,
  units: number,
  move: (dx: number, dy: number) => void,
  done: () => void,
): () => void {
  el.setPointerCapture(e.pointerId);
  const [x0, y0] = [e.clientX, e.clientY];
  const onMove = (ev: Event) => {
    const p = ev as PointerEvent;
    if (p.pointerId === e.pointerId) move((p.clientX - x0) * units, (p.clientY - y0) * units);
  };
  const stop = () => {
    el.removeEventListener('pointermove', onMove);
    el.removeEventListener('pointerup', end);
    el.removeEventListener('pointercancel', end);
  };
  const end = (ev: Event) => {
    if ((ev as PointerEvent).pointerId !== e.pointerId) return;
    stop();
    done();
  };
  el.addEventListener('pointermove', onMove);
  el.addEventListener('pointerup', end);
  el.addEventListener('pointercancel', end);
  return stop;
}
