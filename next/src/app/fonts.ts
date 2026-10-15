/** The site's faces (docs/site.md §3), self-hosted through next/font as `--serif` and `--mono`. */
import localFont from 'next/font/local';

export const serif = localFont({
  src: [
    { path: '../assets/fonts/eb-garamond-roman.woff2', weight: '400 800', style: 'normal' },
    { path: '../assets/fonts/eb-garamond-italic.woff2', weight: '400 800', style: 'italic' },
  ],
  variable: '--serif',
  display: 'swap',
  fallback: ['Garamond', 'Times New Roman', 'serif'],
  adjustFontFallback: 'Times New Roman',
});

export const mono = localFont({
  src: [{ path: '../assets/fonts/walldye-mono.woff2', weight: '400 700', style: 'normal' }],
  variable: '--mono',
  display: 'swap',
  fallback: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
  adjustFontFallback: false,
});
