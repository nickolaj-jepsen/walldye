/** Whether an element has come within a viewport of the visible area, for lazy plates. */
import { type RefObject, useEffect, useState } from 'react';

/**
 * True once `ref`'s element has come within one viewport height of the view, and from then on;
 * always true when `lazy` is false. What is observed is the element's grid row (`<li>`) when it
 * has one, else its `<svg>` for an SVG child, else the element.
 */
export function useNear(ref: RefObject<Element | null>, lazy: boolean): boolean {
  const [near, setNear] = useState(!lazy);
  useEffect(() => {
    const el = ref.current;
    if (near || !el) return;
    // A row that content-visibility skips lays out none of its content, so the plate never
    // intersects; and a <g> with nothing drawn yet has no box, while its <svg> has the plate's.
    const svg = el instanceof SVGElement ? el.ownerSVGElement : null;
    const target = el.closest('li') ?? svg ?? el;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) setNear(true);
      },
      { rootMargin: '100% 0px' },
    );
    io.observe(target);
    return () => io.disconnect();
  }, [ref, near]);
  return near;
}
