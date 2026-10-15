'use client';
/** The Versions choice: each version's name over its 16:9 picture, a radio group. */
import { Plate } from '../plate/Plate';
import styles from './Detail.module.css';
import { useDetail } from './detail-context';

export function Versions() {
  const { piece, version, chooseVersion } = useDetail();
  return (
    <section aria-labelledby="versions-h">
      <h2 id="versions-h" className="sc">
        Versions
      </h2>
      <div
        className={`seg ${styles.versions}`}
        id="versions"
        role="radiogroup"
        aria-labelledby="versions-h"
      >
        {piece.versions.map((v) => (
          <label key={v.name}>
            <input
              type="radio"
              name="v"
              value={v.name}
              checked={v.name === version.name}
              onChange={() => chooseVersion(v.name)}
            />
            <span>{v.label}</span>
            <span className={styles.thumb} aria-hidden="true">
              <Plate slug={piece.slug} data={v.plates['16:9']} alt="" />
            </span>
          </label>
        ))}
      </div>
    </section>
  );
}
