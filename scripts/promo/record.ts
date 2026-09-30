/**
 * Records the site's promo loop as `promo/walldye.mp4` (1920×1080), `.webp` and `.gif` (1280×720):
 * the downloaded wallpaper shrinks into its index plate, the index runs through a few themes and the
 * phone shape, the plate carries to its page (the site's own view transition), Download is pressed,
 * and the file it saves recolors back to the first frame. Stills come from headless Chromium; the
 * cursor, the crossfades and the zooms between file and page are composited frame by frame, so every
 * run gives the same film.
 *
 * pnpm promo [--piece <slug>] [--skip-build] [--stills]
 *
 * Needs a built catalog (`walldye build --all --published`), ffmpeg, and Chromium for Playwright;
 * `nix develop` has all but the catalog. img2webp and gifski make the WebP and the GIF. The
 * piece must be on the index's first screen at 1440×810 (featured.yaml). With `stats/` checked out
 * the index's sort shows the view orders, as on walldye.com.
 */
import { type ChildProcess, spawn, spawnSync } from 'node:child_process';
import { once } from 'node:events';
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { parseArgs } from 'node:util';
import { type Browser, chromium, type Page } from '@playwright/test';
import sharp from 'sharp';

const { values: args } = parseArgs({
  options: {
    piece: { type: 'string', default: 'nix-snowflake' },
    'skip-build': { type: 'boolean', default: false },
    stills: { type: 'boolean', default: false },
  },
});
const PIECE = args.piece;
const OUT = 'promo';
const PORT = 4411;
const BASE = `http://127.0.0.1:${PORT}`;

const FPS = 30;
// The layout offsets below (REST, SCROLL) are for this viewport.
const W = 1440;
const H = 810;
const S = 4 / 3;
const OW = W * S;
const OH = H * S;
/** Where the cursor rests on the index, beside the results line. */
const REST: [number, number] = [930, 168];
/** Hovers nothing, so a capture there shows no hover state. */
const NEUTRAL: [number, number] = [2, 2];
/** How far the detail page is scrolled to lift the Download line off the frame's bottom edge, CSS px. */
const SCROLL = 88;
/** The index's color row, in order; the last is the theme the rest of the film is in. */
const INDEX_THEMES = [
  '[data-family="catppuccin"]',
  '[data-family="solarized"]',
  '[data-preset="nord"]',
  '[data-family="rose-pine"]',
];
/** The downloaded file's colors: the index's last theme, one more, then fireproof, the theme the index opens in and the film's first frame. */
const FILE_THEMES = ['rose-pine', 'nord', 'fireproof'] as const;

type Rgb = Buffer;
interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}
interface Picture {
  data: Rgb;
  w: number;
  h: number;
}
/** What the page records about a view transition, for the film to step through it. */
interface Probe {
  __vtAnims?: Animation[];
  __imgFade?: Animation[];
  __imgAt?: number;
}

// ---- setup -----------------------------------------------------------------

/** Whether `tool` runs; ffmpeg and img2webp take `-version`, gifski `--version`. */
function need(tool: string, flag = '--version'): boolean {
  return spawnSync(tool, [flag], { stdio: 'ignore' }).status === 0;
}

function run(cmd: string, argv: string[]): void {
  const r = spawnSync(cmd, argv, { stdio: 'inherit' });
  if (r.status !== 0) throw new Error(`${cmd} ${argv.join(' ')} failed`);
}

/** `astro preview` on PORT, resolved once it answers; kill the returned process group when done. */
async function serve(): Promise<ChildProcess> {
  const server = spawn(
    'pnpm',
    ['astro', 'preview', '--ignore-lock', '--host', '127.0.0.1', '--port', `${PORT}`],
    {
      stdio: 'ignore',
      detached: true,
    },
  );
  for (let i = 0; i < 100; i++) {
    try {
      if ((await fetch(`${BASE}/`)).ok) return server;
    } catch {
      // not up yet
    }
    await new Promise((r) => setTimeout(r, 200));
  }
  stop(server);
  throw new Error(`astro preview did not answer on ${BASE}`);
}

function stop(server: ChildProcess): void {
  if (server.pid) {
    try {
      process.kill(-server.pid);
    } catch {
      // already gone
    }
  }
}

// ---- output ----------------------------------------------------------------

class Reel {
  frames = 0;
  private ff: ChildProcess;

  constructor(path: string) {
    this.ff = spawn(
      'ffmpeg',
      [
        '-loglevel',
        'error',
        '-y',
        '-f',
        'rawvideo',
        '-pix_fmt',
        'rgb24',
        '-s',
        `${OW}x${OH}`,
        '-r',
        `${FPS}`,
        '-i',
        '-',
        '-c:v',
        'ffv1',
        path,
      ],
      { stdio: ['pipe', 'inherit', 'inherit'] },
    );
  }

  async write(frame: Rgb): Promise<void> {
    this.frames++;
    const stdin = this.ff.stdin;
    if (stdin && !stdin.write(frame)) await once(stdin, 'drain');
  }

  async close(): Promise<void> {
    this.ff.stdin?.end();
    await once(this.ff, 'close');
  }
}

/**
 * The lossless master as walldye.mp4 (BT.709, tagged, as browsers expect) and, 1280 wide, with
 * img2webp walldye.webp (the README's `.github/promo.webp`) and with gifski walldye.gif. Each is
 * skipped with a warning when its tool is missing.
 */
function encode(master: string, work: string): string[] {
  const mp4 = join(OUT, 'walldye.mp4');
  run('ffmpeg', [
    ...['-loglevel', 'error', '-y', '-i', master],
    ...['-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p'],
    ...['-colorspace', 'bt709', '-color_primaries', 'bt709'],
    ...['-color_trc', 'bt709', '-color_range', 'tv'],
    ...['-c:v', 'libx264', '-preset', 'slow', '-crf', '14', '-tune', 'animation'],
    ...['-x264-params', 'colorprim=bt709:transfer=bt709:colormatrix=bt709'],
    ...['-movflags', '+faststart', mp4],
  ]);
  const wrote = [mp4];
  const webp = need('img2webp', '-version');
  const gif = need('gifski');
  if (!webp) console.warn('img2webp (libwebp) not found: skipping walldye.webp');
  if (!gif) console.warn('gifski not found: skipping walldye.gif');
  if (!webp && !gif) return wrote;

  const dir = join(work, 'frames');
  mkdirSync(dir);
  run('ffmpeg', [
    '-loglevel',
    'error',
    '-i',
    master,
    '-vf',
    'scale=1280:-1:flags=lanczos',
    join(dir, '%04d.png'),
  ]);
  const files = readdirSync(dir)
    .sort()
    .map((f) => join(dir, f));

  if (webp) {
    // Near-lossless: libwebp's lossy frames each patch the last with pixels it deems close enough, so ghosts pile up.
    const argv = ['-loop', '0', '-near_lossless', '40', '-m', '4'];
    let prev: Buffer | null = null;
    let from = 0;
    const flush = (i: number): void => {
      // Durations in whole ms, rounded against the clock so the loop keeps FPS.
      const ms = Math.round((i * 1000) / FPS) - Math.round((from * 1000) / FPS);
      argv.push('-d', `${ms}`, files[from]);
    };
    for (const [i, f] of files.entries()) {
      const png = readFileSync(f);
      if (prev?.equals(png)) continue;
      if (prev) flush(i);
      prev = png;
      from = i;
    }
    flush(files.length);
    const out = join(OUT, 'walldye.webp');
    run('img2webp', [...argv, '-o', out]);
    wrote.push(out);
  }
  if (gif) {
    const out = join(OUT, 'walldye.gif');
    // Full quality turns off gifski's reuse of the previous frame's pixels, which leaves ghosts of each crossfade.
    run('gifski', [
      ...['--quiet', '--width', '1280', '--fps', `${FPS}`],
      ...['--quality', '100', '--motion-quality', '100', '--lossy-quality', '100'],
      ...['-o', out, ...files],
    ]);
    wrote.push(out);
  }
  return wrote;
}

// ---- pixels ----------------------------------------------------------------

const n = (sec: number): number => Math.max(1, Math.round(sec * FPS));
const ease = (t: number): number => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);
const easeOut = (t: number): number => 1 - (1 - t) ** 3;
const lerp = (a: number, b: number, t: number): number => a + (b - a) * t;
const FULL: Rect = { x: 0, y: 0, w: OW, h: OH };

function mix(a: Rgb, b: Rgb, t: number): Rgb {
  const out = Buffer.allocUnsafe(a.length);
  for (let i = 0; i < a.length; i++) out[i] = a[i] + (b[i] - a[i]) * t + 0.5;
  return out;
}

function lerpRect(a: Rect, b: Rect, t: number): Rect {
  return { x: lerp(a.x, b.x, t), y: lerp(a.y, b.y, t), w: lerp(a.w, b.w, t), h: lerp(a.h, b.h, t) };
}

/** Output px of a CSS-px box, inset by the plate's 1px frame. */
function outRect(b: { x: number; y: number; width: number; height: number }): Rect {
  return { x: (b.x + 1) * S, y: (b.y + 1) * S, w: (b.width - 2) * S, h: (b.height - 2) * S };
}

/** Copies `pic` scaled into `r` of `frame` at opacity `alpha`. Edges are rounded, not sizes, so they don't jitter. */
async function paste(frame: Rgb, pic: Picture, r: Rect, alpha = 1): Promise<void> {
  const x0 = Math.round(r.x);
  const y0 = Math.round(r.y);
  const w = Math.round(r.x + r.w) - x0;
  const h = Math.round(r.y + r.h) - y0;
  const tile = await sharp(pic.data, { raw: { width: pic.w, height: pic.h, channels: 3 } })
    .resize(w, h, { fit: 'fill' })
    .raw()
    .toBuffer();
  for (let j = 0; j < h; j++) {
    const fy = y0 + j;
    if (fy < 0 || fy >= OH) continue;
    for (let i = 0; i < w; i++) {
      const fx = x0 + i;
      if (fx < 0 || fx >= OW) continue;
      const si = (j * w + i) * 3;
      const di = (fy * OW + fx) * 3;
      for (let k = 0; k < 3; k++)
        frame[di + k] = frame[di + k] + (tile[si + k] - frame[di + k]) * alpha + 0.5;
    }
  }
}

const ARROW = (
  s: number,
): string => `<svg xmlns="http://www.w3.org/2000/svg" width="${Math.ceil(26 * s)}" height="${Math.ceil(30 * s)}" viewBox="-2 -2 26 30">
  <path d="M0 0 L0 20.5 L5 15.8 L8.4 23.6 L11.6 22.2 L8.3 14.6 L15 14.6 Z" fill="#111" stroke="#fff" stroke-width="1.4" stroke-linejoin="round"/></svg>`;

interface Cursor {
  data: Buffer;
  w: number;
  h: number;
  /** The tip's offset from the image's corner, output px. */
  hot: number;
}

async function cursor(scale: number): Promise<Cursor> {
  const { data, info } = await sharp(Buffer.from(ARROW(scale)))
    .ensureAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });
  return { data, w: info.width, h: info.height, hot: 2 * scale };
}

// ---- the film's state and moves --------------------------------------------

class Film {
  /** The picture as it stands, before the cursor. */
  still: Rgb = Buffer.alloc(OW * OH * 3);
  cx = REST[0];
  cy = REST[1];
  cursorAlpha = 0;
  readonly page: Page;
  private reel: Reel;
  private arrows: { up: Cursor; down: Cursor };
  private stills: string | null;
  private stillNo = 0;

  constructor(page: Page, reel: Reel, arrows: { up: Cursor; down: Cursor }, stills: string | null) {
    this.page = page;
    this.reel = reel;
    this.arrows = arrows;
    this.stills = stills;
  }

  save(label: string, png: Buffer): void {
    if (this.stills)
      writeFileSync(
        join(this.stills, `${String(this.stillNo++).padStart(2, '0')}-${label}.png`),
        png,
      );
  }

  async capture(label: string): Promise<Rgb> {
    const png = await this.page.screenshot({ type: 'png' });
    this.save(label, png);
    return sharp(png).removeAlpha().raw().toBuffer();
  }

  /** The page with the real mouse parked where it hovers nothing. */
  async unhovered(label: string): Promise<Rgb> {
    await this.page.mouse.move(...NEUTRAL);
    await this.page.waitForTimeout(80);
    return this.capture(label);
  }

  async emit(base: Rgb, pressed = false): Promise<void> {
    const f = Buffer.from(base);
    if (this.cursorAlpha > 0) this.drawCursor(f, pressed ? this.arrows.down : this.arrows.up);
    await this.reel.write(f);
  }

  private drawCursor(frame: Rgb, c: Cursor): void {
    const ox = Math.round(this.cx * S - c.hot);
    const oy = Math.round(this.cy * S - c.hot);
    for (let j = 0; j < c.h; j++) {
      const fy = oy + j;
      if (fy < 0 || fy >= OH) continue;
      for (let i = 0; i < c.w; i++) {
        const fx = ox + i;
        if (fx < 0 || fx >= OW) continue;
        const si = (j * c.w + i) * 4;
        const a = (c.data[si + 3] / 255) * this.cursorAlpha;
        if (a === 0) continue;
        const di = (fy * OW + fx) * 3;
        for (let k = 0; k < 3; k++)
          frame[di + k] = frame[di + k] * (1 - a) + c.data[si + k] * a + 0.5;
      }
    }
  }

  async hold(sec: number): Promise<void> {
    for (let i = 0; i < n(sec); i++) await this.emit(this.still);
  }

  /** Crossfades to `next`, ramping the cursor's opacity to `alpha`. */
  async fadeTo(next: Rgb, sec: number, alpha = this.cursorAlpha): Promise<void> {
    const k = n(sec);
    const a0 = this.cursorAlpha;
    for (let i = 1; i <= k; i++) {
      const t = easeOut(i / k);
      this.cursorAlpha = lerp(a0, alpha, t);
      await this.emit(mix(this.still, next, t));
    }
    this.still = next;
  }

  /**
   * Moves `pic` from rect `a` to `b` over the current still, which cuts to `next`. The picture blends in
   * over `fadeIn` frames and out over `fadeOut`, so pasted pixels never pop against the page's own.
   */
  async moveTile(
    pic: Picture,
    a: Rect,
    b: Rect,
    next: Rgb,
    sec: number,
    { cursorTo = this.cursorAlpha, fadeIn = 3, fadeOut = 0 } = {},
  ): Promise<void> {
    const k = n(sec);
    const a0 = this.cursorAlpha;
    for (let i = 1; i <= k; i++) {
      this.cursorAlpha = lerp(a0, cursorTo, Math.min(1, (i / k) * 2));
      const f = Buffer.from(next);
      const alpha = Math.min(1, i / fadeIn, fadeOut ? (k - i) / fadeOut : 1);
      if (alpha > 0) await paste(f, pic, lerpRect(a, b, ease(i / k)), alpha);
      await this.emit(f);
    }
    this.cursorAlpha = cursorTo;
    this.still = next;
  }

  /** Glides the cursor to (x, y), CSS px, on a slight arc timed by distance; hover states it leaves fade out. */
  async glide(x: number, y: number): Promise<void> {
    const [x0, y0] = [this.cx, this.cy];
    const [dx, dy] = [x - x0, y - y0];
    const len = Math.hypot(dx, dy) || 1;
    const bow = Math.min(60, len * 0.08);
    const k = n(Math.min(0.95, Math.max(0.3, 0.3 + len / 1600)));
    const left = await this.unhovered('leave');
    const from = this.still;
    for (let i = 1; i <= k; i++) {
      const t = ease(i / k);
      const off = Math.sin(Math.PI * t) * bow;
      this.cx = x0 + dx * t + (-dy / len) * off;
      this.cy = y0 + dy * t + (dx / len) * off;
      await this.emit(i <= 3 ? mix(from, left, i / 3) : left);
    }
    this.still = left;
    [this.cx, this.cy] = [x, y];
    await this.page.mouse.move(x, y);
  }

  async box(sel: string): Promise<{ x: number; y: number; width: number; height: number }> {
    const b = await this.page.locator(sel).first().boundingBox();
    if (!b) throw new Error(`no box for ${sel}`);
    return b;
  }

  async centre(sel: string, dx = 0, dy = 0): Promise<[number, number]> {
    const b = await this.box(sel);
    return [b.x + b.width / 2 + dx, b.y + b.height / 2 + dy];
  }

  /** Waits for the page to finish recoloring what is in view. */
  async settle(ms = 700): Promise<void> {
    await this.page.waitForTimeout(ms);
    await this.page.evaluate(() =>
      Promise.all(
        [...document.images]
          .filter((i) => i.getBoundingClientRect().top < innerHeight)
          .map((i) => i.decode().catch(() => {})),
      ),
    );
    await this.page.waitForTimeout(120);
  }

  /** Glides to `sel`, shows its hover, dwells and holds the press down, then runs `act`. */
  async press(
    sel: string,
    act: (x: number, y: number) => Promise<unknown>,
    { dx = 0, dy = 0 } = {},
  ): Promise<void> {
    const [x, y] = await this.centre(sel, dx, dy);
    await this.glide(x, y);
    await this.settle(60);
    await this.fadeTo(await this.capture('hover'), 0.1);
    await this.hold(0.12);
    for (let i = 0; i < 4; i++) await this.emit(this.still, true);
    await act(x, y);
  }

  /** press() with a click, then fades to the page as it is after it while the press releases. */
  async click(sel: string, { fade = 0.22, dx = 0, dy = 0, label = 'click' } = {}): Promise<void> {
    await this.press(sel, (x, y) => this.page.mouse.click(x, y), { dx, dy });
    await this.settle();
    const after = await this.capture(label);
    const k = n(fade);
    const before = this.still;
    for (let i = 1; i <= k; i++) await this.emit(mix(before, after, easeOut(i / k)), i < 2);
    this.still = after;
  }
}

// ---- recording ---------------------------------------------------------------

/** The piece as Download saves it on its page, in each theme. */
async function downloads(
  browser: Browser,
  themes: readonly string[],
  film: Film | null,
): Promise<Record<string, Picture>> {
  const ctx = await browser.newContext({
    viewport: { width: W, height: H },
    deviceScaleFactor: S,
    colorScheme: 'dark',
    reducedMotion: 'reduce',
  });
  const p = await ctx.newPage();
  const out: Record<string, Picture> = {};
  for (const t of themes) {
    await p.goto(`${BASE}/${PIECE}?t=${t}`, { waitUntil: 'networkidle' });
    await p.waitForTimeout(500);
    const [dl] = await Promise.all([p.waitForEvent('download'), p.click('#quick-download')]);
    const file = await dl.path();
    const { data, info } = await sharp(file)
      .removeAlpha()
      .raw()
      .toBuffer({ resolveWithObject: true });
    if (info.width !== OW || info.height !== OH)
      throw new Error(`the ${t} download is ${info.width}×${info.height}, not ${OW}×${OH}`);
    film?.save(`download-${t}`, readFileSync(file));
    out[t] = { data, w: OW, h: OH };
  }
  await ctx.close();
  return out;
}

async function record(browser: Browser, master: string, stills: string | null): Promise<number> {
  const ctx = await browser.newContext({
    viewport: { width: W, height: H },
    deviceScaleFactor: S,
    colorScheme: 'dark',
    // The site's own motion stays on: its plate transition is recorded as it runs.
    reducedMotion: 'no-preference',
    acceptDownloads: true,
  });
  // On a view transition: pause its animations once they start, and the arriving plate's own fade when
  // its picture goes in, noting when that was, so the film can step through both.
  await ctx.addInitScript(() => {
    const w = window as unknown as Probe;
    addEventListener('pagereveal', (e) => {
      const vt = e.viewTransition;
      if (!vt) return;
      const t0 = performance.now();
      const plate = document.querySelector('.spread .plate');
      if (plate) {
        const mo = new MutationObserver(() => {
          const img = plate.querySelector(':scope > img');
          if (!img) return;
          mo.disconnect();
          w.__imgFade = img.getAnimations();
          for (const a of w.__imgFade) a.pause();
          w.__imgAt = performance.now() - t0;
        });
        mo.observe(plate, { childList: true });
      }
      vt.ready.then(() => {
        w.__vtAnims = document
          .getAnimations()
          .filter((a) =>
            (a.effect as KeyframeEffect | null)?.pseudoElement?.startsWith('::view-transition'),
          );
        for (const a of w.__vtAnims) a.pause();
      });
    });
  });
  const page = await ctx.newPage();
  const reel = new Reel(master);
  const film = new Film(page, reel, { up: await cursor(S), down: await cursor(S * 0.86) }, stills);
  const file = await downloads(browser, FILE_THEMES, film);
  const first = file.fireproof;

  await page.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await film.settle(900);
  const plateSel = `li[data-slug="${PIECE}"] .plate img`;
  const onFirstScreen = await page
    .locator(plateSel)
    .evaluate((el) => el.getBoundingClientRect().bottom <= innerHeight)
    .catch(() => false);
  if (!onFirstScreen)
    throw new Error(
      `${PIECE} is not on the index's first screen: move it up featured.yaml, or pass --piece`,
    );
  const index = await film.unhovered('index');

  // the wallpaper, then where it comes from
  film.still = first.data;
  await film.hold(0.8);
  await film.moveTile(first, FULL, outRect(await film.box(plateSel)), index, 0.75, {
    fadeIn: 1,
    fadeOut: 3,
  });
  await film.hold(0.2);
  await film.fadeTo(index, 0.3, 1);
  await film.hold(0.2);

  // every plate follows the theme
  for (const sel of INDEX_THEMES) {
    await film.click(`.themes button${sel}`, { label: sel.replace(/\W/g, '') });
    await film.hold(0.3);
  }
  await film.hold(0.3);

  // any screen: the site reflows at once, so a cut
  await film.click('label:has(> input[name=shape][value="9x19.5"])', {
    label: '9x19.5',
    fade: 0.01,
    dx: -12,
    dy: 6,
  });
  await film.hold(1.0);
  await film.click('label:has(> input[name=shape][value="16x9"])', {
    label: '16x9',
    fade: 0.01,
    dx: -12,
    dy: 6,
  });
  await film.hold(0.35);

  // the site carries the plate to its page: its own view transition, stepped at the film's frame rate
  await film.press(`li[data-slug="${PIECE}"] figure`, (x, y) =>
    Promise.all([page.waitForURL(`**/${PIECE}**`), page.mouse.click(x, y)]),
  );
  await page.waitForFunction(() => ((window as unknown as Probe).__vtAnims?.length ?? 0) > 0);
  await page.waitForFunction(() => (window as unknown as Probe).__imgAt !== undefined, null, {
    timeout: 10_000,
  });
  const { total, imgAt } = await page.evaluate(() => {
    const p = window as unknown as Required<Probe>;
    return {
      total: Math.max(...p.__vtAnims.map((a) => Number(a.effect?.getComputedTiming().endTime))),
      imgAt: p.__imgAt,
    };
  });
  console.log(`view transition: ${total} ms, the arriving picture in at ${imgAt.toFixed(0)} ms`);
  for (let i = 0; i * (1000 / FPS) <= total; i++) {
    const t = i * (1000 / FPS);
    await page.evaluate(
      ([t, imgAt]) => {
        const p = window as unknown as Required<Probe>;
        for (const a of p.__vtAnims) a.currentTime = t;
        for (const a of p.__imgFade) a.currentTime = Math.max(0, t - imgAt);
      },
      [t, imgAt],
    );
    await page.waitForTimeout(30);
    film.still = await film.capture(`transition-${i}`);
    await film.emit(film.still, i < 1);
  }
  await page.evaluate(() => {
    const p = window as unknown as Required<Probe>;
    for (const a of [...p.__vtAnims, ...p.__imgFade]) a.play();
  });
  await film.settle(600);
  await film.fadeTo(await film.capture('detail'), 0.06);
  await film.hold(0.35);
  {
    const k = n(0.4);
    for (let i = 1; i <= k; i++) {
      await page.evaluate((y) => window.scrollTo(0, y), Math.round(SCROLL * ease(i / k)));
      await page.waitForTimeout(20);
      film.still = await film.capture(`scroll-${i}`);
      await film.emit(film.still);
    }
  }
  const big = outRect(await film.box('.spread .plate img'));
  await film.hold(0.4);

  // its download, and the file it makes
  await film.press(
    '#quick-download .k',
    (x, y) => Promise.all([page.waitForEvent('download'), page.mouse.click(x, y)]),
    { dx: -8, dy: 2 },
  );
  await film.emit(film.still);
  await film.hold(0.1);
  const [shown, ...rest] = FILE_THEMES;
  await film.moveTile(file[shown], big, FULL, film.still, 0.6, { cursorTo: 0 });
  film.still = file[shown].data;
  await film.hold(0.7);

  // the same file in other colors, back to the first frame
  for (const [i, t] of rest.entries()) {
    await film.fadeTo(file[t].data, 0.22);
    await film.hold(i < rest.length - 1 ? 0.5 : 0.3);
  }

  await reel.close();
  await ctx.close();
  return reel.frames;
}

// ---- main ------------------------------------------------------------------

if (!need('ffmpeg', '-version'))
  throw new Error('ffmpeg not found: run this inside `nix develop`, or install it');
if (!args['skip-build']) run('pnpm', ['astro', 'build']);
if (!existsSync('dist/index.html'))
  throw new Error('no dist/: build the site first, or drop --skip-build');
if (!existsSync('stats'))
  console.warn('no stats/: the index sort shows no view orders (docs/deploy.md, Page views)');

mkdirSync(OUT, { recursive: true });
const work = mkdtempSync(join(tmpdir(), 'walldye-promo-'));
const stills = args.stills ? join(OUT, 'stills') : null;
if (stills) {
  rmSync(stills, { recursive: true, force: true });
  mkdirSync(stills);
}
const server = await serve();
try {
  const browser = await chromium.launch();
  try {
    const master = join(work, 'master.mkv');
    const frames = await record(browser, master, stills);
    console.log(`${frames} frames, ${(frames / FPS).toFixed(2)} s`);
    console.log(`wrote ${encode(master, work).join(', ')}`);
  } finally {
    await browser.close();
  }
} finally {
  stop(server);
  rmSync(work, { recursive: true, force: true });
}
