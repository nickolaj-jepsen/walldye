/** Social cards: scripts/cards.ts draws one per piece at build time into public/og/. */

export const CARD_W = 1200;
export const CARD_H = 630;

/** Where the card of the piece `slug` is served. */
export function cardUrl(slug: string): string {
  return `/og/${slug}.png`;
}

/** A piece's card as Next's `openGraph.images` entry; `alt` is the piece's alt text. */
export function cardImage(slug: string, alt: string) {
  return { url: cardUrl(slug), width: CARD_W, height: CARD_H, alt, type: 'image/png' };
}
