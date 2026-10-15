'use client';
/**
 * The Export panel's Crop row, while the chosen shape is cropped from 16:9: the range, and where the
 * plate shows the crop itself (phones, tall shapes) a small 16:9 map with the crop window over it.
 */
import { Plate } from '../plate/Plate';
import { CropWindow } from './CropWindow';
import styles from './Detail.module.css';
import { useDetail } from './detail-context';

export function CropRow() {
  const { piece, version, native, inPlace, shape, setCrop } = useDetail();
  if (native) return null;
  return (
    <div className={`row center ${inPlace ? styles.cropRowMap : ''}`} id="crop-row">
      <span className="k">Crop</span>
      <div>
        {inPlace && (
          <div className={styles.cropMap} aria-hidden="true">
            <Plate slug={piece.slug} data={version.plates['16:9']} alt="">
              <CropWindow />
            </Plate>
          </div>
        )}
        <input
          className="range"
          id="crop"
          type="range"
          min={0}
          max={1}
          step={0.001}
          value={shape.t}
          aria-label="Crop position"
          onChange={(e) => setCrop(Number(e.currentTarget.value))}
        />
      </div>
    </div>
  );
}
