'use client';
/** The listing's "Copy" button: puts design.py on the clipboard, then says so for two seconds. */
import { useEffect, useRef, useState } from 'react';
import { copyText } from '../../client/clipboard';

const FLASH_MS = 2000;

export function CopySource({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const timer = useRef(0);
  useEffect(() => () => clearTimeout(timer.current), []);

  async function copy() {
    if (!(await copyText(text))) return;
    setCopied(true);
    clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setCopied(false), FLASH_MS);
  }

  return (
    <button type="button" className="textbtn" data-action="copy-source" onClick={copy}>
      {copied ? 'Copied' : 'Copy'}
    </button>
  );
}
