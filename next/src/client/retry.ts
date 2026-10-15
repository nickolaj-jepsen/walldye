/** Waits before each retry of a failed load; after the last, only the `online` event retries. */
export const RETRY_MS: readonly number[] = [1_000, 3_000, 10_000, 30_000];

interface Callbacks {
  /** After the task resolves. */
  done?: () => void;
  /** After each failure, before the retry is scheduled. */
  failed?: () => void;
}

/**
 * Runs `task` until it resolves: after its nth failure it runs again RETRY_MS[n] later, and at once
 * when the browser comes back online. Returns a function that stops it; once stopped, or after
 * success, no callback fires again.
 */
export function retrying(
  task: () => Promise<unknown>,
  { done, failed }: Callbacks = {},
): () => void {
  let live = true;
  let running = false;
  let failures = 0;
  let timer = 0;
  const stop = () => {
    live = false;
    clearTimeout(timer);
    removeEventListener('online', online);
  };
  const run = () => {
    clearTimeout(timer);
    if (!live || running) return;
    running = true;
    task()
      .then(
        () => {
          if (!live) return;
          stop();
          done?.();
        },
        () => {
          if (!live) return;
          failed?.();
          if (failures < RETRY_MS.length) timer = window.setTimeout(run, RETRY_MS[failures++]);
        },
      )
      .finally(() => {
        running = false;
      });
  };
  const online = () => {
    failures = 0;
    run();
  };
  addEventListener('online', online);
  run();
  return stop;
}
