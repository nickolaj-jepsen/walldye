'use client';
/**
 * The crop window over a plate showing the whole 16:9 picture (the detail plate, or the crop map on
 * phones): a frame around the chosen shape's crop that drags along the crop axis. The Crop range is
 * the keyboard control.
 */
import type { PointerEvent } from 'react';
import { cropAxis, cropSpan } from '../../lib/shape';
import { useDetail } from './detail-context';
import { dragCrop } from './drag';
import { cropWindowStyle } from './state';

export function CropWindow() {
  const { shape, setCrop } = useDetail();
  const onPointerDown = (e: PointerEvent<HTMLDivElement>) => {
    const plate = e.currentTarget.parentElement;
    if (e.button !== 0 || !plate) return;
    e.preventDefault();
    const picture =
      cropAxis(shape.aspect) === 'x'
        ? plate.clientWidth
        : (plate.querySelector('.pic')?.getBoundingClientRect().height ?? 0);
    const travel = picture * (1 - cropSpan(shape.aspect));
    dragCrop(e.currentTarget, e.nativeEvent, shape.aspect, shape.t, travel, setCrop);
  };
  return (
    <div
      className="crop"
      data-axis={cropAxis(shape.aspect)}
      style={cropWindowStyle(shape)}
      onPointerDown={onPointerDown}
    >
      <span className="handle" />
    </div>
  );
}
