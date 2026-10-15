/** The Sources list. A caption-cited source's link back never wraps away from the entry's last word. */
import { captionSources, type Piece } from '../../lib/content';
import styles from './Detail.module.css';

export function Footnotes({ piece: p }: { piece: Pick<Piece, 'sources'> }) {
  const cited = new Set(captionSources(p)?.items.map((c) => c.n) ?? []);
  return (
    <ol className={`footnotes ${styles.footnotes}`}>
      {p.sources.map((s, i) => {
        const n = i + 1;
        const name = s.title ?? s.topic;
        const work = s.title !== undefined;
        const year =
          s.year === undefined ? '' : `${s.author || s.title || s.topic ? ', ' : ''}${s.year}`;
        const sep = s.author && (s.title || s.topic) ? ', ' : '';
        const named =
          name && (work ? <i lang={s.lang}>{name}</i> : <span lang={s.lang}>{name}</span>);
        return (
          <li key={n} id={`fn${n}`}>
            <span>
              {s.url && !name ? <a href={s.url}>{s.author}</a> : s.author}
              {sep}
              {named && (s.url ? <a href={s.url}>{named}</a> : named)}
              {year}
              {cited.has(n) ? (
                <span className="nowrap">
                  .{' '}
                  <a href={`#fnref${n}`} className="back" aria-label="Back to text">
                    ↑
                  </a>
                </span>
              ) : (
                '.'
              )}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
