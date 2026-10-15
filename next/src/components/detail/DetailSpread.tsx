'use client';
/**
 * The detail page's plate in the chosen shape: a composed shape's own template centered in the 16:9
 * picture, a cropped one as the 16:9 picture under the crop window, or on phones a tall shape as the
 * plate itself (a cropped one moves under a sideways drag). A piece with a motif gets a handle over
 * it that moves the motif, corners that resize it and a two-finger pinch anywhere on the plate; a
 * drag moves the motif layer by a CSS transform and writes the placement to the address on release.
 * The `f` key shows the plate full screen.
 */
import { type CSSProperties, type PointerEvent, useEffect, useRef, useState } from 'react';
import { CANVAS } from '../../lib/content';
import {
  clampPlacement,
  drawnPlacement,
  type Placement,
  pinchMotif,
  placedBox,
  resizeMotif,
} from '../../lib/motif';
import { cropBox } from '../../lib/shape';
import { Plate } from '../plate/Plate';
import { CropWindow } from './CropWindow';
import styles from './Detail.module.css';
import { useDetail, useMotifPreview } from './detail-context';
import { dragCrop, dragMotif } from './drag';
import { MotifRows } from './MotifRows';
import { boxStyle, canvasRect, isTall, motifShift } from './state';

const CORNERS = ['0,0', '1,0', '0,1', '1,1'] as const;

function toggleFullscreen(el: Element | null | undefined): void {
  if (!el || !document.fullscreenEnabled || typeof el.requestFullscreen !== 'function') return;
  if (document.fullscreenElement) void document.exitFullscreen();
  else el.requestFullscreen().catch(() => {});
}

export function DetailSpread() {
  const d = useDetail();
  const { preview, setPreview } = useMotifPreview();
  const figure = useRef<HTMLElement>(null);
  const canvas = useRef<HTMLDivElement>(null);
  const handle = useRef<HTMLSpanElement>(null);
  /** The placement the drag in progress shows, which its end writes. */
  const latest = useRef<Placement | null>(null);
  /** Touches on the plate by pointer id, in client pixels. */
  const touches = useRef(new Map<number, [number, number]>());
  /** The pinch in progress: the placement it began from, its fingers' midpoint and spread in canvas units. */
  const pinch = useRef<{ from: Placement; m0: [number, number]; d0: number } | null>(null);
  /** Drops the one-pointer drag in progress, which a pinch takes over. */
  const stopDrag = useRef<(() => void) | null>(null);
  // On a touch screen the handle stays framed, with its corners, until a touch lands elsewhere.
  const [touched, setTouched] = useState(false);

  const { piece, version, shape, data, motif: info, source, inPlace, narrow, native } = d;
  const [w, h] = CANVAS[source];
  const [aw, ah] = CANVAS[shape.aspect];
  const tall = isTall(shape.aspect);
  const shown = info ? (preview ?? d.placement ?? drawnPlacement(info)) : null;
  const view = inPlace ? cropBox(shape.aspect, shape.t) : { x: 0, y: 0, w, h };
  // The plate takes a tall shape's ratio on narrow screens (Detail.module.css), else 16:9.
  const frameRatio = narrow && tall ? aw / ah : 16 / 9;
  const composed = native && shape.aspect !== '16:9';

  useEffect(() => {
    const onDown = (e: globalThis.PointerEvent) => {
      if (!handle.current?.contains(e.target as Node)) setTouched(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.repeat || e.altKey || e.ctrlKey || e.metaKey || e.shiftKey)
        return;
      if (document.getElementById('picker')?.matches(':popover-open')) return;
      const target = e.target instanceof Element ? e.target : null;
      if (target?.closest('input, textarea, select, [role=slider], [role=region]')) return;
      if (target instanceof HTMLElement && target.isContentEditable) return;
      if (e.key === 'f' || e.key === 'F') toggleFullscreen(figure.current?.querySelector('.plate'));
    };
    document.addEventListener('pointerdown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('pointerdown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, []);

  /** Shows the motif at `p` until the drag ends. */
  const previewMotif = (p: Placement) => {
    if (!info) return;
    const next = clampPlacement(info, aw, ah, p);
    latest.current = next;
    setPreview(next);
  };

  /** Writes the previewed placement, which the plate then draws itself. */
  const commitMotif = () => {
    const p = latest.current;
    if (!p) return;
    latest.current = null;
    setPreview(null);
    d.setMotif({ at: [p.x, p.y], scale: p.k });
  };

  /** The first two touches' midpoint and distance, in canvas units. */
  const fingers = () => {
    const [a, b] = touches.current.values();
    const c = canvas.current;
    if (!c || !a || !b) return undefined;
    const r = c.getBoundingClientRect();
    const units = w / r.width;
    const m: [number, number] = [
      ((a[0] + b[0]) / 2 - r.left) * units,
      ((a[1] + b[1]) / 2 - r.top) * units,
    ];
    return { m, d: Math.hypot(a[0] - b[0], a[1] - b[1]) * units };
  };

  // The handle moves the motif; a corner of it resizes the motif about the opposite corner.
  const onHandleDown = (e: PointerEvent<HTMLSpanElement>) => {
    // A second finger joins the pinch the plate starts.
    if (e.pointerType === 'touch' && touches.current.size > 0) return;
    const c = canvas.current;
    if (e.button !== 0 || !info || !shown || !c?.clientWidth) return;
    e.preventDefault();
    if (e.pointerType !== 'mouse') setTouched(true);
    const units = w / c.clientWidth;
    const from = shown;
    const corner = (e.target as Element).closest<HTMLElement>('.motif-corner')?.dataset.corner;
    if (!corner) {
      const move = (dx: number, dy: number) =>
        previewMotif({ ...from, x: from.x + dx, y: from.y + dy });
      stopDrag.current = dragMotif(e.currentTarget, e.nativeEvent, units, move, commitMotif);
      return;
    }
    const k = [Number(corner[0]), Number(corner[2])] as const;
    const [hx, hy, hw, hh] = info.handle;
    const [px, py] = [from.x + (hx + k[0] * hw) * from.k, from.y + (hy + k[1] * hh) * from.k];
    const resize = (dx: number, dy: number) =>
      previewMotif(resizeMotif(info, w, h, from, k, [px + dx, py + dy]));
    stopDrag.current = dragMotif(e.currentTarget, e.nativeEvent, units, resize, commitMotif);
  };

  // Two fingers anywhere on the plate pinch the motif; one drags a crop shown in place.
  const onPlateDown = (e: PointerEvent<HTMLElement>) => {
    const target = e.target as Element;
    const plate = target.closest('.plate');
    if (!plate) return;
    if (info && shown && e.pointerType === 'touch') {
      touches.current.set(e.pointerId, [e.clientX, e.clientY]);
      const f = touches.current.size === 2 ? fingers() : undefined;
      if (f) {
        e.preventDefault();
        stopDrag.current?.();
        stopDrag.current = null;
        setTouched(true);
        pinch.current = { from: shown, m0: f.m, d0: f.d };
        return;
      }
    }
    if (e.button !== 0 || !inPlace || target.closest('.motif-handle')) return;
    const pic = plate.querySelector('.pic')?.getBoundingClientRect();
    if (!pic) return;
    e.preventDefault();
    // The plate shows the crop itself, so the picture moves under the drag and the crop runs against it.
    const travel = (pic.height * 16) / 9 - pic.width;
    dragCrop(plate, e.nativeEvent, shape.aspect, shape.t, travel, d.setCrop, true);
  };

  const onPlateMove = (e: PointerEvent<HTMLElement>) => {
    if (!touches.current.has(e.pointerId)) return;
    touches.current.set(e.pointerId, [e.clientX, e.clientY]);
    const p = pinch.current;
    const f = fingers();
    if (!p || !info || !f) return;
    previewMotif(pinchMotif(info, w, h, p.from, p.m0, p.d0, f.m, f.d));
  };

  const onPlateLift = (e: PointerEvent<HTMLElement>) => {
    if (!touches.current.delete(e.pointerId) || !pinch.current) return;
    pinch.current = null;
    commitMotif();
  };

  const motifStyle: CSSProperties | undefined =
    preview && info
      ? {
          transform: motifShift(d.placement ?? drawnPlacement(info), preview),
          transformOrigin: '0 0',
        }
      : undefined;

  return (
    <>
      <figure
        ref={figure}
        className={`spread ${styles.spread}`}
        data-aspect={shape.aspect}
        data-tall={tall ? '' : undefined}
        style={{ '--shape-ratio': aw / ah } as CSSProperties}
        onPointerDown={onPlateDown}
        onPointerMove={onPlateMove}
        onPointerUp={onPlateLift}
        onPointerCancel={onPlateLift}
      >
        <Plate
          slug={piece.slug}
          data={data}
          alt={version.alt}
          view={view}
          placement={d.placement}
          motifStyle={motifStyle}
          className={composed ? styles.composed : inPlace ? styles.inPlace : undefined}
          style={composed ? ({ '--shape': aw / ah } as CSSProperties) : undefined}
          transitionName={`plate-${piece.slug}`}
        >
          {!native && !inPlace && <CropWindow />}
          {info && shown && (
            <div className="motif-frame" data-touched={touched ? '' : undefined} aria-hidden="true">
              <div
                className="motif-canvas"
                ref={canvas}
                style={{ ...canvasRect(view, w, h, frameRatio), translate: 'none' }}
              >
                <span
                  className="motif-handle"
                  ref={handle}
                  style={boxStyle(placedBox(info.handle, shown), w, h)}
                  onPointerDown={onHandleDown}
                >
                  {CORNERS.map((c) => (
                    <span key={c} className="motif-corner" data-corner={c} />
                  ))}
                </span>
              </div>
            </div>
          )}
        </Plate>
      </figure>
      {/* Narrow screens take the motif's rows from Export to here, beside the picture they move. */}
      {piece.motif && (
        <div className={`motif-near ${styles.motifNear}`}>{narrow && <MotifRows />}</div>
      )}
    </>
  );
}
