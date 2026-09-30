/**
 * The inline <head> script (Base.astro bundles it) that carries a piece's plate between a grid and
 * its page as a cross-document view transition. Only that one plate is named, since the browser
 * captures every named element; any other navigation skips the transition. It must run before the
 * first render, when pagereveal fires.
 */

let named: HTMLElement | null = null;

/** The piece a navigation carries: the one it opens, or the one it leaves for the index. */
function slugCarried(from: URL, to: URL): string | undefined {
  const slug = (u: URL) => /^\/([a-z0-9][a-z0-9-]*)$/.exec(u.pathname)?.[1];
  if (from.origin !== to.origin || from.pathname === to.pathname) return undefined;
  return slug(to) ?? (to.pathname === '/' ? slug(from) : undefined);
}

function carry(vt: ViewTransition | null, from?: string | null, to?: string | null): void {
  // A page back from the back/forward cache still names the plate it carried away.
  if (named) named.style.viewTransitionName = '';
  named = null;
  if (!vt) return;
  const slug = from && to ? slugCarried(new URL(from), new URL(to)) : undefined;
  named = slug
    ? document.querySelector<HTMLElement>(
        `.spread .plate[data-plate="${slug}"], .grid > li[data-slug="${slug}"] .plate`,
      )
    : null;
  if (named) named.style.viewTransitionName = 'plate';
  else vt.skipTransition();
}

addEventListener('pageswap', (e) =>
  carry(e.viewTransition, location.href, e.activation?.entry.url),
);
addEventListener('pagereveal', (e) => {
  carry(e.viewTransition, self.navigation?.activation?.from?.url, location.href);
  e.viewTransition?.finished.then(() => carry(null));
});
