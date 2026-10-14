/**
 * The detail plate's motif: the handle a visitor drags, and while a placement changes, live layers
 * (the picture without the motif, and the motif alone) that move without redrawing the picture.
 */
import { type Aspect, CANVAS } from '../../lib/content';
import {
  type MotifInfo,
  motifAlone,
  motifGround,
  motifWindow,
  type Placement,
  placedBox,
} from '../../lib/motif';

/** `el` over the canvas-unit `box` of a `w`×`h` canvas, in percentages of the canvas. */
function cover(el: HTMLElement, box: readonly number[], w: number, h: number): void {
  Object.assign(el.style, {
    left: `${(box[0] / w) * 100}%`,
    top: `${(box[1] / h) * 100}%`,
    width: `${(box[2] / w) * 100}%`,
    height: `${(box[3] / h) * 100}%`,
  });
}

function image(svg: string, cls: string): HTMLImageElement {
  const img = new Image();
  img.alt = '';
  img.className = cls;
  img.decoding = 'async';
  img.src = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml' }));
  return img;
}

function drop(img: HTMLImageElement | undefined): void {
  if (!img) return;
  img.remove();
  URL.revokeObjectURL(img.src);
}

/** The plate's `.motif-frame`, its handle and its live layers. */
export class MotifView {
  readonly frame: HTMLElement;
  readonly canvas: HTMLElement;
  readonly handle: HTMLElement;
  private ground?: HTMLImageElement;
  private alone?: HTMLImageElement;
  private window: number[] = [];
  private size: readonly [number, number] = CANVAS['16:9'];
  /** The placement place() showed last, which layers that finish decoding take. */
  private latest: Placement = { x: 0, y: 0, k: 1 };
  private generation = 0;
  /** The live template text and motif, kept to cut an overscan motif's next window from. */
  private source?: { text: string; info: MotifInfo };
  private recutting = false;

  constructor(frame: HTMLElement) {
    this.frame = frame;
    this.canvas = frame.querySelector<HTMLElement>('.motif-canvas') ?? frame;
    this.handle = frame.querySelector<HTMLElement>('.motif-handle') ?? frame;
  }

  /** Whether live layers are showing (or being made). */
  get live(): boolean {
    return this.generation % 2 === 1;
  }

  /** Shows the handle for `info` placed at `p` on an `aspect` canvas, or hides the frame without a motif. */
  place(info: MotifInfo | undefined, aspect: Aspect, p: Placement): void {
    this.frame.hidden = !info;
    if (!info) return;
    const [w, h] = CANVAS[aspect];
    this.size = [w, h];
    this.latest = p;
    this.canvas.style.setProperty('--canvas-ratio', String(w / h));
    cover(this.handle, placedBox(info.handle, p), w, h);
    if (!this.alone) return;
    const [x, y, bw, bh] = placedBox(this.window, p);
    cover(this.alone, [x, y, bw, bh], w, h);
    // An overscan motif's window that no longer reaches every edge is cut again around `p`.
    const short = x > 0 || y > 0 || x + bw < w || y + bh < h;
    if (this.source?.info.overscan && short) void this.recut();
  }

  /** Swaps the motif layer for one cut around the latest placement, once it is decoded. */
  private async recut(): Promise<void> {
    if (this.recutting || !this.source) return;
    this.recutting = true;
    const gen = this.generation;
    const [w, h] = this.size;
    const window = motifWindow(this.source.info, w, h, this.latest);
    const alone = image(motifAlone(this.source.text, window), 'alone');
    await alone.decode().catch(() => {});
    this.recutting = false;
    if (gen !== this.generation || !this.alone) return drop(alone);
    this.alone.replaceWith(alone);
    drop(this.alone);
    this.alone = alone;
    this.window = window;
    cover(alone, placedBox(window, this.latest), w, h);
  }

  /**
   * Starts live layers cut from `svg`, the recolored template `info` describes, placed at `p`: they
   * show once both images are decoded, unless stop() ran meanwhile. Does nothing while live.
   */
  async start(svg: Promise<string>, info: MotifInfo, p: Placement): Promise<void> {
    if (this.live) return;
    const gen = ++this.generation;
    const [w, h] = this.size;
    this.window = motifWindow(info, w, h, p);
    const text = await svg.catch(() => undefined);
    if (text === undefined || gen !== this.generation) return;
    const ground = image(motifGround(text), 'ground');
    const alone = image(motifAlone(text, this.window), 'alone');
    cover(alone, placedBox(this.window, p), w, h);
    await Promise.all([ground.decode(), alone.decode()]).catch(() => {});
    if (gen !== this.generation) {
      drop(ground);
      drop(alone);
      return;
    }
    this.ground = ground;
    this.alone = alone;
    this.source = { text, info };
    cover(alone, placedBox(this.window, this.latest), w, h);
    this.canvas.prepend(ground, alone);
  }

  /** Removes the live layers, leaving the plate's own picture. */
  stop(): void {
    if (this.live) this.generation++;
    drop(this.ground);
    drop(this.alone);
    this.ground = this.alone = this.source = undefined;
  }
}

/**
 * Follows the drag `e` starts on `el`, calling `move` with how far that pointer has gone, in canvas
 * units at `units` per pixel, then `done` when it ends. Returns a function that drops the drag
 * without calling `done`.
 */
export function dragMotif(
  el: HTMLElement,
  e: PointerEvent,
  units: number,
  move: (dx: number, dy: number) => void,
  done: () => void,
): () => void {
  el.setPointerCapture(e.pointerId);
  const [x0, y0] = [e.clientX, e.clientY];
  const onMove = (ev: PointerEvent) => {
    if (ev.pointerId === e.pointerId) move((ev.clientX - x0) * units, (ev.clientY - y0) * units);
  };
  const stop = () => {
    el.removeEventListener('pointermove', onMove);
    el.removeEventListener('pointerup', end);
    el.removeEventListener('pointercancel', end);
  };
  const end = (ev: PointerEvent) => {
    if (ev.pointerId !== e.pointerId) return;
    stop();
    done();
  };
  el.addEventListener('pointermove', onMove);
  el.addEventListener('pointerup', end);
  el.addEventListener('pointercancel', end);
  return stop;
}
