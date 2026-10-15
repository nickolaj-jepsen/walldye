'use client';
/** The Export panel's Shape row: every site shape, and a note when the chosen one is cropped from 16:9. */
import { SITE_ASPECTS } from '../../lib/content';
import { useDetail } from './detail-context';

export function ShapeRow() {
  const { piece, state, native, chooseAspect } = useDetail();
  return (
    <div className="row">
      <span className="k">Shape</span>
      <div className="seg" role="radiogroup" aria-label="Shape">
        {SITE_ASPECTS.map((a) => (
          <label key={a}>
            <input
              type="radio"
              name="asp"
              value={a}
              data-native={piece.aspects.includes(a) ? '' : undefined}
              checked={a === state.aspect}
              onChange={() => chooseAspect(a)}
            />
            <span>
              <span className="mono">{a}</span>
            </span>
          </label>
        ))}
      </div>
      {!native && (
        <span className="sub hint" id="shape-hint">
          cropped from <span className="mono">16:9</span>
        </span>
      )}
    </div>
  );
}
