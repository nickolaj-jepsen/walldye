import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  applyTheme,
  clearShared,
  followChanges,
  ownChoice,
  ownTheme,
  PAGE_ATTR,
  resolveTheme,
  STORAGE_KEY,
  SYSTEM_PAIR,
  savePair,
  saveTheme,
  sharedDiffers,
  THEME_EVENT,
  takeSharedParam,
} from '../../src/client/theme/store';
import { faviconUrl } from '../../src/lib/favicon';
import { cssVars, normalizeSeeds, PRESETS } from '../../src/lib/theme';
import { inlineScript } from '../../src/server/inline-script';

class MemoryStorage {
  data = new Map<string, string>();
  getItem(k: string) {
    return this.data.get(k) ?? null;
  }
  setItem(k: string, v: string) {
    this.data.set(k, v);
  }
  removeItem(k: string) {
    this.data.delete(k);
  }
}

const blocked = {
  getItem() {
    throw new DOMException('denied', 'SecurityError');
  },
  setItem() {
    throw new DOMException('denied', 'SecurityError');
  },
  removeItem() {
    throw new DOMException('denied', 'SecurityError');
  },
};

interface Env {
  session: MemoryStorage;
  local: MemoryStorage;
  props: Map<string, string>;
  dataset: Record<string, string>;
  favicon: Map<string, string>;
  events: string[];
  replaced: string[];
  schemeListeners: (() => void)[];
  windowListeners: [string, (e: Event) => void][];
  setLight(light: boolean): void;
}

/** Browser globals the theme store touches, backed by plain objects. */
function stubBrowser(href: string, light = false): Env {
  const env: Env = {
    session: new MemoryStorage(),
    local: new MemoryStorage(),
    props: new Map(),
    dataset: {},
    favicon: new Map(),
    events: [],
    replaced: [],
    schemeListeners: [],
    windowListeners: [],
    setLight(value) {
      light = value;
      for (const fn of env.schemeListeners) fn();
    },
  };
  vi.stubGlobal('sessionStorage', env.session);
  vi.stubGlobal('localStorage', env.local);
  vi.stubGlobal('location', { href });
  vi.stubGlobal('history', {
    state: { kept: 1 },
    replaceState: (_s: unknown, _t: string, url: string) => env.replaced.push(url),
  });
  vi.stubGlobal('matchMedia', (query: string) => ({
    get matches() {
      return query === '(prefers-color-scheme: light)' && light;
    },
    addEventListener: (_type: string, fn: () => void) => env.schemeListeners.push(fn),
  }));
  vi.stubGlobal('addEventListener', (type: string, fn: (e: Event) => void) =>
    env.windowListeners.push([type, fn]),
  );
  vi.stubGlobal('document', {
    documentElement: {
      style: { setProperty: (k: string, v: string) => env.props.set(k, v) },
      dataset: env.dataset,
    },
    getElementById: (id: string) =>
      id === 'favicon' ? { setAttribute: (k: string, v: string) => env.favicon.set(k, v) } : null,
    dispatchEvent: (e: CustomEvent) => env.events.push(`${e.type} ${e.detail}`),
  });
  return env;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('resolution and persistence', () => {
  let env: Env;
  beforeEach(() => {
    env = stubBrowser('https://walldye.com/schotter');
  });

  it('follows the system scheme while nothing is shared or saved', () => {
    expect(resolveTheme()).toMatchObject({ token: 'fireproof', source: 'system' });
    stubBrowser('https://walldye.com/', true);
    expect(resolveTheme()).toMatchObject({ token: 'flexoki-light', source: 'system' });
  });

  it('prefers the saved theme, then a shared one', () => {
    env.local.setItem(STORAGE_KEY, 'nord');
    expect(resolveTheme()).toMatchObject({ token: 'nord', source: 'saved' });
    env.session.setItem(STORAGE_KEY, 'ffffff-000000-ff8800');
    expect(resolveTheme()).toMatchObject({
      token: 'ffffff-000000-ff8800',
      source: 'shared',
      seeds: { accent: '#FF8800' },
    });
    expect(sharedDiffers()).toBe(true);
    env.session.setItem(STORAGE_KEY, 'nord');
    expect(sharedDiffers()).toBe(false);
  });

  it('follows the system scheme within a saved pair', () => {
    savePair(['gruvbox-dark', '282828-ebdbb2-fe8019']);
    expect(env.local.getItem(STORAGE_KEY)).toBe('pair:gruvbox-dark,gruvbox-dark');
    savePair(['gruvbox-dark', 'gruvbox-light']);
    expect(env.local.getItem(STORAGE_KEY)).toBe('pair:gruvbox-dark,gruvbox-light');
    expect(ownChoice()).toEqual({ pair: ['gruvbox-dark', 'gruvbox-light'] });
    expect(resolveTheme()).toMatchObject({ token: 'gruvbox-dark', source: 'saved' });
    followChanges();
    env.setLight(true);
    expect(resolveTheme().token).toBe('gruvbox-light');
    expect(env.dataset.theme).toBe('gruvbox-light');
  });

  it('saving the system pair goes back to the system theme', () => {
    env.local.setItem(STORAGE_KEY, 'nord');
    env.session.setItem(STORAGE_KEY, 'dracula');
    expect(ownChoice()).toEqual({ token: 'nord' });
    savePair(SYSTEM_PAIR);
    expect(env.local.getItem(STORAGE_KEY)).toBeNull();
    expect(env.session.getItem(STORAGE_KEY)).toBeNull();
    expect(ownChoice()).toEqual({ pair: SYSTEM_PAIR });
    expect(resolveTheme()).toMatchObject({ token: 'fireproof', source: 'system' });
  });

  it('refuses a pair that does not parse, and ignores one stored', () => {
    expect(() => savePair(['nord', 'Nord'])).toThrow(/Nord/);
    for (const bad of ['pair:nord', 'pair:nord,nope', 'pair:nord,dracula,nord', 'family:gruvbox']) {
      env.local.setItem(STORAGE_KEY, bad);
      expect(ownChoice(), bad).toEqual({ pair: SYSTEM_PAIR });
      expect(resolveTheme().source, bad).toBe('system');
    }
  });

  it('ignores invalid stored values', () => {
    env.local.setItem(STORAGE_KEY, 'Nord');
    env.session.setItem(STORAGE_KEY, 'bg=#000,fg=#fff,accent=#f00');
    expect(resolveTheme()).toMatchObject({ token: 'fireproof', source: 'system' });
  });

  it('treats blocked storage as empty', () => {
    vi.stubGlobal('localStorage', blocked);
    vi.stubGlobal('sessionStorage', blocked);
    expect(resolveTheme()).toMatchObject({ token: 'fireproof', source: 'system' });
    expect(() => clearShared()).not.toThrow();
  });

  it('keeps a shared or saved theme on the page when storage cannot hold it', () => {
    for (const store of [
      blocked,
      { ...new MemoryStorage(), getItem: () => null, setItem: blocked.setItem, removeItem() {} },
    ]) {
      env = stubBrowser('https://walldye.com/?t=nord');
      vi.stubGlobal('sessionStorage', store);
      vi.stubGlobal('localStorage', store);
      takeSharedParam();
      expect(env.replaced).toEqual(['https://walldye.com/']);
      expect(env.dataset[PAGE_ATTR.sessionStorage]).toBe('nord');
      expect(resolveTheme()).toMatchObject({ token: 'nord', source: 'shared' });
      expect(sharedDiffers()).toBe(true);

      saveTheme(PRESETS.dracula);
      expect(env.dataset[PAGE_ATTR.sessionStorage]).toBeUndefined();
      expect(resolveTheme()).toMatchObject({ token: 'dracula', source: 'saved' });
      expect(ownTheme().token).toBe('dracula');
    }
  });

  it('prefers the page copy over an older stored token, and drops it once a write succeeds', () => {
    env.session.setItem(STORAGE_KEY, 'nord');
    env.dataset[PAGE_ATTR.sessionStorage] = 'dracula';
    expect(resolveTheme().token).toBe('dracula');
    clearShared();
    expect(env.dataset[PAGE_ATTR.sessionStorage]).toBeUndefined();
    expect(resolveTheme().source).toBe('system');
  });

  it('copies a valid ?t= into the session and strips it from the address', () => {
    env = stubBrowser('https://walldye.com/schotter?crop=0.4&t=2E3440-ECEFF4-88c0d0#x');
    takeSharedParam();
    expect(env.session.getItem(STORAGE_KEY)).toBe('nord');
    expect(env.local.getItem(STORAGE_KEY)).toBeNull();
    expect(env.replaced).toEqual(['https://walldye.com/schotter?crop=0.4#x']);
    expect(resolveTheme().source).toBe('shared');
  });

  it('strips an invalid ?t= without storing it, and leaves addresses without one alone', () => {
    env = stubBrowser('https://walldye.com/?t=nord,accent=f00');
    takeSharedParam();
    expect(env.session.getItem(STORAGE_KEY)).toBeNull();
    expect(env.replaced).toEqual(['https://walldye.com/']);
    env = stubBrowser('https://walldye.com/about');
    takeSharedParam();
    expect(env.replaced).toEqual([]);
  });

  it('saving keeps the theme and ends the shared one', () => {
    env.session.setItem(STORAGE_KEY, 'nord');
    saveTheme(normalizeSeeds({ bg: '#FFF', fg: '#000', accent: '#f80' }));
    expect(env.local.getItem(STORAGE_KEY)).toBe('ffffff-000000-ff8800');
    expect(env.session.getItem(STORAGE_KEY)).toBeNull();
  });

  it('applies every color property, the regime, the token, the icon and an event', () => {
    applyTheme(PRESETS['solarized-light']);
    expect(Object.fromEntries(env.props)).toEqual(cssVars(PRESETS['solarized-light']));
    expect(env.dataset.regime).toBe('light');
    expect(env.dataset.theme).toBe('solarized-light');
    expect(env.favicon.get('href')).toBe(faviconUrl(PRESETS['solarized-light']));
    expect(env.events).toEqual([`${THEME_EVENT} solarized-light`]);
  });

  it('follows a scheme change while nothing is saved, and re-applies a saved or shared theme so listeners re-check', () => {
    followChanges();
    env.setLight(true);
    expect(env.dataset.regime).toBe('light');
    expect(env.props.get('--bg')).toBe('#FFFCF0');
    env.local.setItem(STORAGE_KEY, 'nord');
    env.setLight(false);
    expect(env.props.get('--bg')).toBe('#2E3440');
    env.session.setItem(STORAGE_KEY, 'flexoki-light');
    env.setLight(true);
    expect(env.props.get('--bg')).toBe('#FFFCF0');
    expect(env.events).toEqual([
      `${THEME_EVENT} flexoki-light`,
      `${THEME_EVENT} nord`,
      `${THEME_EVENT} flexoki-light`,
    ]);
  });

  it('re-resolves a page restored from the back/forward cache', () => {
    followChanges();
    const pageshow = env.windowListeners
      .filter(([type]) => type === 'pageshow')
      .map(([, fn]) => fn);
    expect(pageshow).toHaveLength(1);
    env.local.setItem(STORAGE_KEY, 'nord');
    pageshow[0]({ persisted: false } as unknown as Event);
    expect(env.events).toEqual([]);
    pageshow[0]({ persisted: true } as unknown as Event);
    expect(env.props.get('--bg')).toBe('#2E3440');
    expect(env.events).toEqual([`${THEME_EVENT} nord`]);
  });
});

describe('theme boot', () => {
  // The script Base.astro inlines.
  const bundle = () => inlineScript('theme', false);

  it('stays small', async () => {
    expect((await bundle()).length).toBeLessThan(8 * 1024);
  });

  it('applies a shared theme before paint and strips ?t=', async () => {
    const env = stubBrowser('https://walldye.com/?t=gruvbox-dark');
    new Function(await bundle())();
    expect(env.dataset.regime).toBe('dark');
    expect(env.props.get('--seed-accent')).toBe('#FE8019');
    expect(env.replaced).toEqual(['https://walldye.com/']);
    expect(env.schemeListeners).toHaveLength(1);
  });

  it('keeps going when the address cannot be rewritten or storage is blocked', async () => {
    const env = stubBrowser('https://walldye.com/?t=nord', true);
    vi.stubGlobal('history', {
      replaceState() {
        throw new Error('sandboxed');
      },
    });
    vi.stubGlobal('localStorage', blocked);
    new Function(await bundle())();
    expect(env.props.get('--bg')).toBe('#2E3440');
  });
});
