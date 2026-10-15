'use client';
/**
 * A grid entry's link, which prefetches the page's own content only once the visitor shows intent
 * (pointer over it, focus, a touch): prefetching every entry in view would cost a request per entry.
 * The page must have arrived whole when the navigation first commits, or the plate cannot morph.
 */
import type { Route } from 'next';
import Link from 'next/link';
import { type ComponentProps, useState } from 'react';

type IntentLinkProps = Omit<ComponentProps<typeof Link<Route>>, 'prefetch'>;

// With Partial Prefetching (WALLDYE_LINK_PREFETCH), 'auto' is the route's shared App Shell, one
// request for every link to /[slug], and `true` adds this link's content. The export has no App
// Shell: its default prefetch is the whole page, so nothing is prefetched before intent.
const IDLE = process.env.WALLDYE_LINK_PREFETCH ? 'auto' : false;
const WANTED = process.env.WALLDYE_LINK_PREFETCH ? true : null;

export function IntentLink(props: IntentLinkProps) {
  const [wanted, setWanted] = useState(false);
  const want = () => setWanted(true);
  return (
    <Link
      {...props}
      prefetch={wanted ? WANTED : IDLE}
      onPointerEnter={want}
      onFocus={want}
      onTouchStart={want}
    />
  );
}
