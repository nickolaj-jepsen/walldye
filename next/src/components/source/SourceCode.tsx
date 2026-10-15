/**
 * The "Source code" appendix, closed at first: design.py through Shiki, a Copy button, and the run
 * command. The listing is highlighted once per slug and kept with the catalog's lifetime.
 */
import { cacheLife } from 'next/cache';
import { type ReactNode, Suspense } from 'react';
import { lineCount } from '../../lib/content';
import { highlightDesign } from '../../lib/highlight';
import { getScript } from '../../server/catalog';
import { CopySource } from './CopySource';
import { RunCommand } from './RunCommand';
import styles from './SourceCode.module.css';

export interface SourceCodeProps {
  slug: string;
  /**
   * The render command's text, for a page that tracks the version, shape and crop shown (a
   * RunCommand with those props); the default version's whole 16:9 picture when omitted.
   */
  command?: ReactNode;
}

const REPO = 'https://github.com/nickolaj-jepsen/walldye';

async function Listing({ slug, command }: { slug: string; command: ReactNode }) {
  'use cache';
  cacheLife('catalog');
  const script = await getScript(slug);
  if (script === null)
    return <p className={styles.lost}>The script for this wallpaper has been lost.</p>;
  const html = await highlightDesign(script);
  return (
    <>
      <p className="listing-head">
        <span>
          <span className="mono path">
            wallpapers/
            <wbr />
            {slug}/<wbr />
            design.py
          </span>
          , <span className="nowrap">{lineCount(script)} lines</span>
        </span>
        <CopySource text={script} />
      </p>
      {/* biome-ignore lint/security/noDangerouslySetInnerHtml: Shiki's markup for the catalog's own design.py */}
      <div className="listing" dangerouslySetInnerHTML={{ __html: html }} />
      <div className="run">
        <h3 className="sc">Run it yourself</h3>
        {/* biome-ignore lint/a11y/noNoninteractiveTabindex lint/a11y/useSemanticElements: a named <pre> region that scrolls sideways takes focus so keys can scroll it */}
        <pre tabIndex={0} role="region" aria-label="Run command">
          <code>
            <span className="cmd">
              <span className="prompt">$ </span>git clone {REPO} &amp;&amp; cd walldye
            </span>
            <span className="cmd">
              <span className="prompt">$ </span>
              {command}
            </span>
          </code>
        </pre>
      </div>
    </>
  );
}

export function SourceCode({ slug, command }: SourceCodeProps) {
  return (
    <details className="appendix">
      <summary>
        <h2 id="appendix-h">Source code</h2>
      </summary>
      <Suspense fallback={null}>
        <Listing slug={slug} command={command ?? <RunCommand slug={slug} />} />
      </Suspense>
    </details>
  );
}
