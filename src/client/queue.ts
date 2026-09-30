/**
 * A queue that runs at most `limit` async tasks at once, handing each freed slot to the waiting
 * task nearest the viewport and dropping a waiter that is no longer wanted.
 */

/** A place in a queue. */
export interface Turn {
  /** The element whose distance from the viewport orders the waiters; without one, first come first served. */
  near?: Element;
  /** Whether the task is still wanted, asked while it waits; one no longer wanted rejects. */
  wanted?: () => boolean;
}

interface Waiter extends Turn {
  start: () => void;
  drop: () => void;
}

/** Pixels between `el` and the viewport, 0 when it is in view or there is no element. */
function offscreen(el: Element | undefined): number {
  if (!el) return 0;
  const r = el.getBoundingClientRect();
  return r.bottom < 0 ? -r.bottom : r.top > innerHeight ? r.top - innerHeight : 0;
}

export class Queue {
  #active = 0;
  readonly #waiting = new Set<Waiter>();

  constructor(readonly limit: number) {}

  /**
   * Runs `task` once fewer than `limit` of this queue's tasks are running, the waiter nearest the
   * viewport first. Rejects without running `task` when it stops being wanted while it waits.
   */
  async run<T>(task: () => Promise<T>, turn: Turn = {}): Promise<T> {
    if (this.#active < this.limit) {
      this.#active++;
    } else {
      await new Promise<void>((resolve, reject) => {
        const drop = () => reject(new DOMException('no longer wanted', 'AbortError'));
        this.#waiting.add({ ...turn, start: resolve, drop });
      });
    }
    try {
      return await task();
    } finally {
      this.#release();
    }
  }

  #release(): void {
    let next: Waiter | undefined;
    let gap = Infinity;
    for (const w of this.#waiting) {
      if (w.wanted && !w.wanted()) {
        this.#waiting.delete(w);
        w.drop();
        continue;
      }
      const d = offscreen(w.near);
      if (d < gap) [next, gap] = [w, d];
    }
    // Hand the slot straight to the next waiter so a new caller cannot slip in between.
    if (next) {
      this.#waiting.delete(next);
      next.start();
    } else {
      this.#active--;
    }
  }
}
