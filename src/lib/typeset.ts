/** Typography for the words visitors read: curled quotes, and the notes' italics, acronyms and figures. */

type Meta = Record<string, unknown>;

const isMapping = (v: unknown): v is Meta =>
  typeof v === 'object' && v !== null && !Array.isArray(v);

/**
 * `text` with typewriter quotes turned into typographer's quotes, matching what the notes' Markdown
 * gets: an apostrophe inside or after a word becomes ’ (Baldur’s, players’), a quote opening a word
 * becomes ‘ or “, and a double quote after a word or punctuation becomes ”. Quotes after figures,
 * such as feet, inches and lignes (16½'''), stay as they are.
 */
export function smartQuotes(text: string): string {
  return text
    .replace(/(?<=[\p{L}\p{N}])'(?=\p{L})|(?<=\p{L})'/gu, '’')
    .replace(/(?<=^|[\s([{—–-])'(?=\d\ds\b)/gu, '’')
    .replace(/(?<=^|[\s([{—–-])'(?=\S)/gu, '‘')
    .replace(/(?<=^|[\s([{—–-])"(?=\S)/gu, '“')
    .replace(/(?<=[\p{L}.,;:!?…)\]’])"/gu, '”');
}

/**
 * A copy of `meta` with smartQuotes applied to what visitors read outside the notes: the title,
 * description and alt text, each variant's label, description and alt text, each source's title, topic and author, and the
 * franchise. Values that are not strings are left for the schema to report.
 */
export function typesetMeta(meta: Meta): Meta {
  const q = (v: unknown) => (typeof v === 'string' ? smartQuotes(v) : v);
  const pick = (v: unknown, keys: string[]) =>
    isMapping(v)
      ? { ...v, ...Object.fromEntries(keys.filter((k) => k in v).map((k) => [k, q(v[k])])) }
      : v;
  const out = pick(meta, ['title', 'description', 'alt']) as Meta;
  if (Array.isArray(meta.sources))
    out.sources = meta.sources.map((s) => pick(s, ['title', 'topic', 'author']));
  if ('franchise' in meta) out.franchise = pick(meta.franchise, ['title', 'owner']);
  if (isMapping(meta.variants)) {
    out.variants = Object.fromEntries(
      Object.entries(meta.variants).map(([name, e]) => [
        name,
        pick(e, ['label', 'description', 'alt']),
      ]),
    );
  }
  return out;
}

/** Notes HTML with `<em>` as `<i>` (italics mark titles), acronyms in `<abbr>` and letter-like figures (Z64, 5.5) in `.lnum`; tags, entities and code are left alone. */
export function typesetNotes(html: string): string {
  const skip = /^<(\/?)(code|pre|abbr|kbd|samp)\b/i;
  let depth = 0;
  return html
    .replace(/<(\/?)em>/g, '<$1i>')
    .split(/(<[^>]+>|&#?\w+;)/)
    .map((part) => {
      if (part.startsWith('&')) return part;
      if (part.startsWith('<')) {
        const m = skip.exec(part);
        if (m) depth += m[1] ? -1 : 1;
        return part;
      }
      if (depth > 0) return part;
      return part
        .replace(/\b[A-Z]{2,}\b/g, '<abbr>$&</abbr>')
        .replace(
          /\b(?:(?=[A-Za-z]*\d)(?=\d*[A-Za-z])[A-Za-z\d]+|\d+\.\d+|\d+ ?× ?\d+)\b/g,
          '<span class="lnum">$&</span>',
        );
    })
    .join('');
}
