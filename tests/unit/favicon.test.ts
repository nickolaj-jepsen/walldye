import { describe, expect, it } from 'vitest';
import { faviconColours, faviconSvg, faviconUrl } from '../../src/lib/favicon';
import { PRESETS } from '../../src/lib/theme';

describe('favicon', () => {
  const seeds = PRESETS.fireproof;

  it('puts bg, fg and accent at three corners and a fg/accent blend at the fourth', () => {
    const cells = faviconColours(seeds);
    expect(cells).toHaveLength(16);
    expect(cells[0]).toBe(seeds.bg);
    expect(cells[3]).toBe(seeds.fg);
    expect(cells[12]).toBe(seeds.accent);
    expect(cells[15]).toBe('#D4A18D');
  });

  it('draws one filled cell per colour', () => {
    const svg = faviconSvg(seeds);
    expect(svg.match(/<rect /g)).toHaveLength(16);
    for (const c of faviconColours(seeds)) expect(svg).toContain(`fill="${c}"`);
    expect(decodeURIComponent(faviconUrl(seeds).replace('data:image/svg+xml,', ''))).toBe(svg);
  });

  it('switches to the light seeds under a light system scheme', () => {
    const svg = faviconSvg(seeds, PRESETS['flexoki-light']);
    const [dark, light] = svg.split('@media (prefers-color-scheme: light)');
    expect(dark).toContain(`.c0{fill:${seeds.bg}}`);
    expect(light).toContain(`.c0{fill:${PRESETS['flexoki-light'].bg}}`);
    expect(svg).toContain('class="c15"');
    expect(svg).not.toContain('fill="#');
  });
});
