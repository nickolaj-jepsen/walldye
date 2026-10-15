'use client';
/** "Copy link": copies the page's address with the applied theme as `?t=`, then says so for two seconds. */
import { useEffect, useRef, useState } from 'react';
import { copyText } from '../../client/clipboard';
import { currentSeeds } from '../../client/theme/current';
import { tokenOf } from '../../lib/theme';

const FLASH_MS = 2000;

function currentLink(): string {
  const url = new URL(location.href);
  url.hash = '';
  url.searchParams.set('t', tokenOf(currentSeeds()));
  return url.href;
}

export function CopyLink() {
  const [copied, setCopied] = useState(false);
  const timer = useRef(0);
  useEffect(() => () => clearTimeout(timer.current), []);

  async function copy() {
    if (!(await copyText(currentLink()))) return;
    setCopied(true);
    clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setCopied(false), FLASH_MS);
  }

  return (
    <button type="button" className="textbtn" data-action="copy-link" onClick={copy}>
      {copied ? 'Link copied' : 'Copy link'}
    </button>
  );
}
