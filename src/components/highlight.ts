import { createCssVariablesTheme, createHighlighter } from 'shiki';

const theme = createCssVariablesTheme({ name: 'walldye', variablePrefix: '--shiki-' });
theme.tokenColors?.push(
  // css-variables colours every operator as a keyword, which puts accent on nearly every line.
  { scope: ['keyword.operator'], settings: { foreground: 'var(--shiki-token-punctuation)' } },
  { scope: ['keyword.operator.logical'], settings: { foreground: 'var(--shiki-token-keyword)' } },
  // ...and every identifier inside call parentheses as punctuation.
  { scope: ['meta.function-call.arguments'], settings: { foreground: 'var(--shiki-foreground)' } },
);

let highlighter: ReturnType<typeof createHighlighter> | undefined;

/** design.py as a Shiki `<pre class="shiki walldye">` in the site's CSS-variables theme (docs/site.md §6.10), a focusable named region. */
export async function highlightDesign(code: string): Promise<string> {
  highlighter ??= createHighlighter({ themes: [theme], langs: ['python'] });
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
