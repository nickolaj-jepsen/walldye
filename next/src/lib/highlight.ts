/**
 * design.py through Shiki in the site's CSS-variables theme. Imports come from the @shikijs scope:
 * Next keeps `shiki` itself external, and the Worker bundler then pulls in every grammar it ships.
 * The JavaScript regex engine highlights Python exactly as Oniguruma does, without its wasm.
 */
import {
  createCssVariablesTheme,
  createHighlighterCore,
  type HighlighterCore,
} from '@shikijs/core';
import { createJavaScriptRegexEngine } from '@shikijs/engine-javascript';
import python from '@shikijs/langs/python';

const theme = createCssVariablesTheme({ name: 'walldye', variablePrefix: '--shiki-' });
theme.tokenColors?.push(
  // css-variables colors every operator as a keyword, which puts accent on nearly every line.
  { scope: ['keyword.operator'], settings: { foreground: 'var(--shiki-token-punctuation)' } },
  { scope: ['keyword.operator.logical'], settings: { foreground: 'var(--shiki-token-keyword)' } },
  // ...and every identifier inside call parentheses as punctuation.
  { scope: ['meta.function-call.arguments'], settings: { foreground: 'var(--shiki-foreground)' } },
);

let highlighter: Promise<HighlighterCore> | undefined;

/** design.py as a Shiki `<pre class="shiki walldye">` in the site's CSS-variables theme, a focusable named region. */
export async function highlightDesign(code: string): Promise<string> {
  highlighter ??= createHighlighterCore({
    themes: [theme],
    langs: [python],
    engine: createJavaScriptRegexEngine(),
  });
  return (await highlighter).codeToHtml(code.replace(/\n$/, ''), {
    lang: 'python',
    theme: 'walldye',
    transformers: [
      {
        pre(node) {
          node.properties.role = 'region';
          node.properties['aria-label'] = 'design.py source';
        },
      },
    ],
  });
}
