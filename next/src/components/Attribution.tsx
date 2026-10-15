/** The caption's attribution from captionParts; nothing for pieces whose sources are only references or data. */
import { Fragment } from 'react';
import { captionParts, type Piece } from '../lib/content';

export interface AttributionProps {
  piece: Pick<Piece, 'sources'>;
  /** Add a footnote reference after each source (the detail page's label). */
  refs?: boolean;
}

export function Attribution({ piece, refs = false }: AttributionProps) {
  const caption = captionParts(piece);
  if (!caption) return null;
  return (
    <>
      {caption.lead}
      {caption.parts.map((it) => (
        <Fragment key={it.n}>
          {it.before}
          {it.title && <i lang={it.lang}>{it.title}</i>}
          {it.topic && <span lang={it.lang}>{it.topic}</span>}
          {it.after}
          {refs && (
            <sup>
              <a href={`#fn${it.n}`} id={`fnref${it.n}`} aria-label={`Source ${it.n}`}>
                {it.n}
              </a>
            </sup>
          )}
        </Fragment>
      ))}
    </>
  );
}
