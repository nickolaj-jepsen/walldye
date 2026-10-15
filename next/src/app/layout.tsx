/**
 * Page shell: the theme boot first in `<head>`, then the masthead, the page's `<main>` and the
 * picker, inside nuqs's adapter. Pages render their own `<main id="main">` with its class (`index`,
 * `detail` or `about`).
 */
import type { Metadata, Viewport } from 'next';
import { NuqsAdapter } from 'nuqs/adapters/next/app';
import type { ReactNode } from 'react';
import { Masthead } from '../components/masthead/Masthead';
import { Picker } from '../components/picker/Picker';
import { THEME_BOOT } from '../generated/boot';
import { mono, serif } from './fonts';
import '../styles/site.css';

export const metadata: Metadata = {
  metadataBase: new URL(process.env.SITE_URL || 'https://walldye.com'),
  title: { default: 'Walldye', template: '%s · Walldye' },
  description: 'Wallpapers drawn with code, in colors you choose.',
  openGraph: { siteName: 'Walldye', type: 'website' },
};

// Web Analytics, which ../scripts/views reads; only walldye.com loads it, not preview or version
// hosts. The beacon counts client navigations itself (its SPA mode, on by default, follows pushState).
const BEACON = `if(location.hostname==='walldye.com'){const s=document.createElement('script');s.src='https://static.cloudflareinsights.com/beacon.min.js';s.dataset.cfBeacon='{"token":"2cf013ccbd694cbeaa73ebd1d868b993"}';document.body.append(s)}`;

export const viewport: Viewport = { width: 'device-width', initialScale: 1 };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    // The boot sets the theme's properties and data attributes on <html> before React hydrates.
    <html lang="en" className={`${serif.variable} ${mono.variable}`} suppressHydrationWarning>
      <head>
        {/* The icon without JavaScript; the boot adds #favicon after it in the visitor’s theme. */}
        <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
        {/* Runs before first paint. React hoists the stylesheets above it, so it waits for them to load. */}
        {/* biome-ignore lint/security/noDangerouslySetInnerHtml: the bundled theme boot, generated at build */}
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT }} />
      </head>
      <body>
        <a className="skip" href="#main">
          Skip to content
        </a>
        <NuqsAdapter>
          <div className="page">
            <Masthead />
            {children}
            <Picker />
          </div>
        </NuqsAdapter>
        {/* biome-ignore lint/security/noDangerouslySetInnerHtml: a constant script of this module */}
        <script dangerouslySetInnerHTML={{ __html: BEACON }} />
      </body>
    </html>
  );
}
