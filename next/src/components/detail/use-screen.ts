/**
 * The visitor's screen for client components: media queries and the screen's size at device
 * resolution, both null during server rendering and hydration.
 */
import { useSyncExternalStore } from 'react';
import { screenPx } from '../../client/screen';

/** Whether `query` matches, or null before hydration. */
export function useMedia(query: string): boolean | null {
  return useSyncExternalStore(
    (onChange) => {
      const mq = matchMedia(query);
      mq.addEventListener('change', onChange);
      return () => mq.removeEventListener('change', onChange);
    },
    () => matchMedia(query).matches,
    () => null,
  );
}

let lastPx: readonly [number, number] | null = null;

/** screenPx(), the same array while the size holds, so it can be a snapshot. */
function pxSnapshot(): readonly [number, number] {
  const [w, h] = screenPx();
  if (!lastPx || lastPx[0] !== w || lastPx[1] !== h) lastPx = [w, h];
  return lastPx;
}

/** The screen in output pixels (screenPx()), or null before hydration; follows rotation and moves between displays. */
export function useScreenPx(): readonly [number, number] | null {
  return useSyncExternalStore(
    (onChange) => {
      addEventListener('resize', onChange);
      return () => removeEventListener('resize', onChange);
    },
    pxSnapshot,
    () => null,
  );
}
