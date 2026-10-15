import { describe, expect, it } from 'vitest';
import { highlightDesign } from './highlight';

describe('highlightDesign', () => {
  const code =
    'from walldye import design\n\n\n@design\ndef draw(c):\n    return c.w * 2 and c.h\n';

  it('is a named, focusable region in the CSS-variables theme', async () => {
    const html = await highlightDesign(code);
    expect(html).toMatch(/^<pre class="shiki walldye"/);
    expect(html).toContain('role="region"');
    expect(html).toContain('aria-label="design.py source"');
    expect(html).toContain('tabindex="0"');
    expect(html).not.toMatch(/#[0-9a-f]{6}/i);
  });

  it('drops one trailing newline and keeps every line', async () => {
    const html = await highlightDesign(code);
    expect(html.match(/class="line"/g)).toHaveLength(6);
  });

  it('colors operators as punctuation and logical operators as keywords', async () => {
    const html = await highlightDesign(code);
    expect(html).toContain('<span style="color:var(--shiki-token-punctuation)">*');
    expect(html).toContain('<span style="color:var(--shiki-token-keyword)"> and');
  });
});
