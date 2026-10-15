/**
 * A piece's page: the plate in the visitor's shape with its crop and motif, the label, the controls,
 * notes and sources, "See also" and the source code. The prerender keeps the start state (default
 * version, 16:9); the address's state (`?v ?shape ?crop ?at ?size`) and the screen's shape take over
 * in the browser.
 */
import type { Metadata } from 'next';
import { cacheLife } from 'next/cache';
import { notFound } from 'next/navigation';
import { Suspense } from 'react';
import { Controls } from '../../components/detail/Controls';
import { DetailSpread } from '../../components/detail/DetailSpread';
import {
  DetailLocal,
  DetailPart,
  type DetailPiece,
  type DetailVersion,
} from '../../components/detail/detail-context';
import { Footnotes } from '../../components/detail/Footnotes';
import { Label } from '../../components/detail/Label';
import { LiveRunCommand } from '../../components/detail/LiveRunCommand';
import { type RelatedPiece, SeeAlso } from '../../components/detail/SeeAlso';
import { ExportRows } from '../../components/export/ExportRows';
import { SourceCode } from '../../components/source/SourceCode';
import { allVersions, type Plates } from '../../lib/catalog';
import { filterGroups, type Piece, relatedPieces } from '../../lib/content';
import { cardImage } from '../../lib/og-card';
import {
  facetLabel,
  getPiece,
  getPieces,
  getSlugs,
  modelName,
  resolvePlate,
} from '../../server/catalog';

export async function generateStaticParams(): Promise<{ slug: string }[]> {
  return (await getSlugs()).map((slug) => ({ slug }));
}

export async function generateMetadata({ params }: PageProps<'/[slug]'>): Promise<Metadata> {
  const p = await getPiece((await params).slug);
  if (!p) return {};
  return {
    title: p.title,
    description: p.description,
    alternates: { canonical: `/${p.slug}` },
    // A page's openGraph replaces the layout's, so siteName is repeated.
    openGraph: {
      siteName: 'Walldye',
      type: 'article',
      title: p.title,
      description: p.description,
      url: `/${p.slug}`,
      images: [cardImage(p.slug, p.alt)],
    },
  };
}

/** Every shape's templates of `plates`, resolved for a Plate. */
function resolveAll(plates: Plates): DetailVersion['plates'] {
  return Object.fromEntries(
    Object.entries(plates).map(([aspect, ref]) => [aspect, resolvePlate(ref)]),
  ) as DetailVersion['plates'];
}

function detailPiece(p: Piece): DetailPiece {
  return {
    slug: p.slug,
    title: p.title,
    license: p.resolvedLicense,
    aspects: p.aspects,
    motif: p.motif,
    versions: allVersions(p).map((v) => ({
      name: v.name,
      label: v.label,
      description: v.description,
      alt: v.alt,
      focus: v.focus,
      plates: resolveAll(v.plates),
    })),
    named: p.versions.length > 0,
  };
}

function relatedPiece(p: Piece): RelatedPiece {
  return {
    slug: p.slug,
    title: p.title,
    alt: p.alt,
    sources: p.sources,
    focus: p.focus,
    plates: resolveAll(p.plates),
    versions: p.versions.map((v) => ({ draft: v.draft })),
  };
}

async function DetailBody({ slug }: { slug: string }) {
  'use cache';
  cacheLife('catalog');
  const p = await getPiece(slug);
  if (!p) notFound();
  const pieces = await getPieces();
  const groups = filterGroups(pieces, facetLabel);
  // Facts link to the index only for values it offers as filters.
  const filters = new Set(groups.flatMap((g) => g.entries.map((e) => `${g.facet}:${e.value}`)));
  // Four fill a row of the grid at desktop widths.
  const related = relatedPieces(p, pieces, 4).map(relatedPiece);
  const piece = detailPiece(p);

  // Only the parts that read the address render twice (DetailPart); the label's text, notes, sources
  // and the listing are prerendered once and hydrated.
  return (
    <main id="main" className="detail">
      <ExportRows piece={p}>
        <DetailLocal>
          <DetailPart piece={piece}>
            <DetailSpread />
          </DetailPart>
          <div className="below">
            <Label
              piece={p}
              detail={piece}
              filters={filters}
              facetLabel={facetLabel}
              modelName={p.model ? modelName(p.model) : undefined}
            />
            <DetailPart piece={piece}>
              <Controls named={piece.named} />
            </DetailPart>
            {(p.notesHtml || p.sources.length > 0) && (
              <div className="label-more">
                {p.notesHtml && (
                  <section className="sect" aria-labelledby="notes-h">
                    <h2 id="notes-h" className="sc hair-t">
                      Notes
                    </h2>
                    {/* biome-ignore lint/security/noDangerouslySetInnerHtml: the piece's own notes, rendered and typeset by codegen */}
                    <div className="prose" dangerouslySetInnerHTML={{ __html: p.notesHtml }} />
                  </section>
                )}
                {p.sources.length > 0 && (
                  <section className="sect" aria-labelledby="sources-h">
                    <h2 id="sources-h" className="sc hair-t">
                      Sources
                    </h2>
                    <Footnotes piece={p} />
                  </section>
                )}
              </div>
            )}
          </div>
          {related.length > 0 && (
            <DetailPart piece={piece}>
              <SeeAlso pieces={related} />
            </DetailPart>
          )}
          <SourceCode
            slug={p.slug}
            command={
              <DetailPart piece={piece}>
                <LiveRunCommand />
              </DetailPart>
            }
          />
        </DetailLocal>
      </ExportRows>
    </main>
  );
}

async function Detail({ params }: { params: PageProps<'/[slug]'>['params'] }) {
  return <DetailBody slug={(await params).slug} />;
}

// Params are read inside Suspense, so a slug outside generateStaticParams streams after a shell.
export default function DetailPage({ params }: PageProps<'/[slug]'>) {
  return (
    <Suspense fallback={<main id="main" className="detail" />}>
      <Detail params={params} />
    </Suspense>
  );
}
