/** The notes Markdown as HTML, through the pipeline Astro's renderMarkdown uses by default (GFM, SmartyPants). */
import rehypeStringify from 'rehype-stringify';
import remarkGfm from 'remark-gfm';
import remarkParse from 'remark-parse';
import remarkRehype from 'remark-rehype';
import remarkSmartypants from 'remark-smartypants';
import { unified } from 'unified';
import { typesetNotes } from '../../src/lib/typeset';

const pipeline = unified()
  .use(remarkParse)
  .use(remarkGfm)
  .use(remarkSmartypants)
  .use(remarkRehype)
  .use(rehypeStringify);

/** `markdown` rendered and typeset (typesetNotes), or null when it is blank. */
export async function renderNotes(markdown: unknown): Promise<string | null> {
  if (typeof markdown !== 'string' || !markdown.trim()) return null;
  return typesetNotes(String(await pipeline.process(markdown)));
}
