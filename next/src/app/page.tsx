/**
 * The index. The filter, sort and shape live in the query string, which only the browser reads, so
 * the prerendered page is the default state (the Suspense fallback) and the browser renders the
 * address's state in its place.
 */
import { cacheLife } from 'next/cache';
import { Suspense } from 'react';
import { FILTER_BOOT, SHAPE_BOOT } from '../components/index/boot';
import type { IndexItem } from '../components/index/filter';
import { IndexBody } from '../components/index/IndexBody';
import { IndexView } from '../components/index/IndexView';
import type { TemplateInfo } from '../lib/catalog';
import { defaultSort, facetPairs, filterGroups, type SortOrder, searchText } from '../lib/content';
import { facetLabel, getPieces, resolvePlate } from '../server/catalog';

async function indexData() {
  'use cache';
  cacheLife('catalog');
  const pieces = await getPieces();
  const sort = defaultSort(pieces);
  // The view orders need a recorded view to mean anything (none in builds without stats/).
  const viewed = pieces.some((p) => p.views > 0);
  const sorts: SortOrder[] = [
    ...(sort === 'featured' ? (['featured'] as const) : []),
    'newest',
    ...(viewed ? (['popular', 'views'] as const) : []),
    'title',
  ];
  const templates: Record<string, TemplateInfo> = {};
  const items = pieces.map((p): IndexItem => {
    for (const ref of Object.values(p.plates)) {
      for (const { hash, ...info } of Object.values(resolvePlate(ref))) templates[hash] = info;
    }
    return {
      slug: p.slug,
      title: p.title,
      added: p.added,
      views: p.views,
      recent: p.recent,
      ...(p.featured === undefined ? {} : { featured: p.featured }),
      alt: p.alt,
      sources: p.sources,
      versions: p.versions.map((v) => ({ draft: v.draft })),
      facets: facetPairs(p),
      search: searchText(p),
      focus: p.focus,
      plates: p.plates,
    };
  });
  return { items, templates, groups: filterGroups(pieces, facetLabel), sorting: { sort, sorts } };
}

export default async function IndexPage() {
  const { sorting, ...data } = await indexData();
  return (
    <main id="main" className="index">
      <h1 className="vh">Index</h1>
      <Suspense
        fallback={
          <IndexBody
            {...data}
            state={{
              q: '',
              sort: sorting.sort,
              shape: '16:9',
              facets: { technique: [], subject: [], lineage: [], other: [] },
            }}
            defaults={{ ...sorting, shape: '16:9' }}
            home="16:9"
            boot={{
              // Phones start with the filter closed; decided before first paint so the grid does not jump.
              // biome-ignore lint/security/noDangerouslySetInnerHtml: a constant script of this module
              filter: <script dangerouslySetInnerHTML={{ __html: FILTER_BOOT }} />,
              // biome-ignore lint/security/noDangerouslySetInnerHtml: a constant script of this module
              shape: <script dangerouslySetInnerHTML={{ __html: SHAPE_BOOT }} />,
            }}
          />
        }
      >
        <IndexView {...data} sorting={sorting} />
      </Suspense>
    </main>
  );
}
