'use client';
/** A masthead nav entry, marked current on its own page. */
import type { Route } from 'next';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import type { ReactNode } from 'react';

export function NavLink({ href, children }: { href: Route; children: ReactNode }) {
  const current = usePathname() === href;
  return (
    <Link className="sc" href={href} aria-current={current ? 'page' : undefined}>
      {children}
    </Link>
  );
}
