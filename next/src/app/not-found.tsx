import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Not found',
  description: 'There is nothing at this address.',
  robots: { index: false },
};

export default function NotFound() {
  return (
    <main id="main" className="about">
      <h1>Not found</h1>
      <div className="prose">
        <p>
          There is nothing at this address. The <Link href="/">index</Link> lists every wallpaper.
        </p>
      </div>
    </main>
  );
}
