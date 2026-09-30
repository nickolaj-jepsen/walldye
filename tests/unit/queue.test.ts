import { describe, expect, it } from 'vitest';
import { Queue } from '../../src/client/queue';

/** A task that resolves to `value` when its returned `finish` is called, logging when it starts. */
function held<T>(log: string[], name: string, value: T) {
  let finish = () => {};
  const task = () =>
    new Promise<T>((resolve) => {
      log.push(name);
      finish = () => resolve(value);
    });
  return { task, finish: () => finish() };
}

const tick = () => new Promise((r) => setTimeout(r, 0));

describe('Queue', () => {
  it('runs at most `limit` tasks at once, the rest in turn as slots free', async () => {
    const q = new Queue(2);
    const log: string[] = [];
    const [a, b, c] = ['a', 'b', 'c'].map((n) => held(log, n, n));
    const results = [q.run(a.task), q.run(b.task), q.run(c.task)];
    await tick();
    expect(log).toEqual(['a', 'b']);
    a.finish();
    await tick();
    expect(log).toEqual(['a', 'b', 'c']);
    b.finish();
    c.finish();
    expect(await Promise.all(results)).toEqual(['a', 'b', 'c']);
  });

  it('drops a waiter that stops being wanted, without running it', async () => {
    const q = new Queue(1);
    const log: string[] = [];
    const a = held(log, 'a', 1);
    let wanted = true;
    const first = q.run(a.task);
    const second = q.run(async () => log.push('b'), { wanted: () => wanted });
    wanted = false;
    a.finish();
    await first;
    await expect(second).rejects.toThrow('no longer wanted');
    expect(log).toEqual(['a']);
    await q.run(async () => log.push('c'));
    expect(log).toEqual(['a', 'c']);
  });
});
