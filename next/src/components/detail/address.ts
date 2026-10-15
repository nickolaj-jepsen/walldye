/** The detail page's query parameters as nuqs parsers; the rules for each value live in ./state. */
import { createParser, parseAsString } from 'nuqs';
import {
  parseAt,
  parseCrop,
  parseScale,
  parseShape,
  writeAt,
  writeCrop,
  writeScale,
  writeShape,
} from './state';

export const detailParams = {
  variant: parseAsString,
  aspect: createParser({ parse: parseShape, serialize: writeShape }),
  crop: createParser({ parse: parseCrop, serialize: writeCrop }),
  at: createParser({
    parse: parseAt,
    serialize: writeAt,
    eq: (a, b) => a[0] === b[0] && a[1] === b[1],
  }),
  scale: createParser({ parse: parseScale, serialize: writeScale }),
};

/** The address's names for the state's keys. */
export const detailKeys = { variant: 'v', aspect: 'shape', scale: 'size' } as const;
