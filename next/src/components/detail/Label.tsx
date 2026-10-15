/**
 * The detail page's label: title, attribution, the Download, the shown version's description, the
 * credit, any license line, and the facts. A fact links to the index only for values it offers as
 * filters (`filters`, `facet:value` pairs). Only the Download and the description read the detail
 * state; the rest is prerendered once.
 */
import type { Route } from 'next';
import Link from 'next/link';
import { Fragment } from 'react';
import { DEFAULT_LICENSE, FAN_WORK } from '../../../scripts/codegen/meta';
import {
  captionSources,
  fitsAnyScreen,
  formatAdded,
  indexQuery,
  type Piece,
} from '../../lib/content';
import { LICENSE_LINES, TAKEDOWN_CONTACT, type TaxonomyFacet } from '../../lib/labels';
import { Attribution } from '../Attribution';
import styles from './Detail.module.css';
import { DetailPart, type DetailPiece } from './detail-context';
import { QuickDownload } from './QuickDownload';
import { VersionDescription } from './VersionText';

export interface LabelProps {
  piece: Piece;
  /** The piece as the detail state's providers take it. */
  detail: DetailPiece;
  /** Every `facet:value` the index offers as a filter. */
  filters: ReadonlySet<string>;
  /** Visitor words for a facet value. */
  facetLabel: (facet: TaxonomyFacet, value: string) => string | undefined;
  /** The credit name of the piece's model, when a model made it. */
  modelName?: string;
}

function Facts({ items }: { items: { label: string; href?: string }[] }) {
  return items.map((f, i) => (
    <Fragment key={f.label}>
      {i > 0 && ', '}
      {f.href ? <Link href={f.href as Route}>{f.label}</Link> : f.label}
    </Fragment>
  ));
}

export function Label({ piece: p, detail, filters, facetLabel, modelName }: LabelProps) {
  const facts = (facet: TaxonomyFacet) =>
    p[facet].map((v) => ({
      label: facetLabel(facet, v) ?? v,
      href: filters.has(`${facet}:${v}`) ? indexQuery(facet, v) : undefined,
    }));
  const technique = facts('technique');
  const lineage = facts('lineage');
  // Figures inside names ("Opus 5.5") take lining numerals.
  const credit = (p.model ? `Made with ${modelName ?? p.model}` : `Made by ${p.author}`)
    .split(/(\S*\d\S*)/)
    .map((text, i) => ({ text, lnum: i % 2 === 1 }));
  const fanWork = p.resolvedLicense === FAN_WORK ? p.franchise : undefined;
  const licenseLine =
    p.resolvedLicense !== DEFAULT_LICENSE && p.resolvedLicense !== FAN_WORK
      ? LICENSE_LINES[p.resolvedLicense]
      : undefined;
  return (
    <div className="label">
      <h1>{p.title}</h1>
      {captionSources(p) && (
        <p className="attr">
          <Attribution piece={p} refs />
        </p>
      )}
      <DetailPart piece={detail}>
        <QuickDownload />
        <VersionDescription />
      </DetailPart>
      <p className="credit">
        {credit.map((c, i) =>
          c.lnum ? (
            // biome-ignore lint/suspicious/noArrayIndexKey: the split never reorders
            <span key={i} className="lnum">
              {c.text}
            </span>
          ) : (
            c.text
          ),
        )}
      </p>
      {fanWork && (
        <p className={`license ${styles.license}`}>
          Unofficial fan tribute, not affiliated with or endorsed by {fanWork.owner}.{' '}
          <i>{fanWork.title}</i> and its characters are trademarks of their owners. Non-commercial;
          contact <a href={`mailto:${TAKEDOWN_CONTACT}`}>{TAKEDOWN_CONTACT}</a> for takedown.
        </p>
      )}
      {licenseLine && <p className={`license ${styles.license}`}>{licenseLine}</p>}
      <dl className="facts hair-t">
        {technique.length > 0 && (
          <>
            <dt>Technique</dt>
            <dd>
              <Facts items={technique} />
            </dd>
          </>
        )}
        {lineage.length > 0 && (
          <>
            <dt>Inspired by</dt>
            <dd>
              <Facts items={lineage} />
            </dd>
          </>
        )}
        <dt>Shape</dt>
        <dd>
          {fitsAnyScreen(p) ? (
            'Any screen'
          ) : (
            <>
              <span className="mono">{p.aspects.join(', ')}</span> (cropped for other screens)
            </>
          )}
        </dd>
        <dt>Added</dt>
        <dd>{formatAdded(p.added)}</dd>
      </dl>
    </div>
  );
}
