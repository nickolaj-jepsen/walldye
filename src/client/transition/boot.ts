/**
 * The inline <head> script (Base.astro bundles it) that carries a plate across navigations. It must run
 * before the first render, since pagereveal fires then, ahead of the page modules. Without support for
 * cross-document view transitions the listeners never fire.
 */

import { onPageReveal, onPageSwap } from './move';

addEventListener('pageswap', (e) => {
  try {
    onPageSwap(e);
  } catch {
    e.viewTransition?.skipTransition();
  }
});
addEventListener('pagereveal', (e) => {
  try {
    onPageReveal(e);
  } catch {
    e.viewTransition?.skipTransition();
  }
});
