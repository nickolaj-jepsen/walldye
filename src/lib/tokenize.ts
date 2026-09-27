/**
 * Paint-context colour tokenizer, a port of walldye/tools/tokenize.py: the one definition of a
 * colour occurrence ("slot"). src/lib/__fixtures__/tokenize.json is the shared spec.
 *
 * A slot is a colour value in a paint context: the attributes fill, stroke, stop-color, flood-color,
 * lighting-color and color, and the same properties inside `style="..."` and `<style>` elements. The
 * value (surrounding whitespace and a CSS `!important` aside) must be exactly hex3, hex6 or a CSS named
 * colour; none, currentColor, url(#id), rgb() and hex with alpha are not slots. Attribute and property
 * names are case-sensitive, hex digits and colour names are not; comments are skipped.
 *
 * Offsets are UTF-16 indices; they equal the Python ones for ASCII input, which templates are.
 */

/** A slot: `svg.slice(start, end)` is the value as written, `colour` its uppercase #RRGGBB. */
export type Slot = [start: number, end: number, colour: string];

export const PAINT = ['fill', 'stroke', 'stop-color', 'flood-color', 'lighting-color', 'color'] as const;
export const SKELETON_MARK = '#';

/** CSS Color 4 named colours, lowercase name -> #RRGGBB. */
export const NAMED: ReadonlyMap<string, string> = new Map(
  (
    'aliceblue:F0F8FF,antiquewhite:FAEBD7,aqua:00FFFF,aquamarine:7FFFD4,azure:F0FFFF,beige:F5F5DC,' +
    'bisque:FFE4C4,black:000000,blanchedalmond:FFEBCD,blue:0000FF,blueviolet:8A2BE2,brown:A52A2A,' +
    'burlywood:DEB887,cadetblue:5F9EA0,chartreuse:7FFF00,chocolate:D2691E,coral:FF7F50,' +
    'cornflowerblue:6495ED,cornsilk:FFF8DC,crimson:DC143C,cyan:00FFFF,darkblue:00008B,darkcyan:008B8B,' +
    'darkgoldenrod:B8860B,darkgray:A9A9A9,darkgreen:006400,darkgrey:A9A9A9,darkkhaki:BDB76B,' +
    'darkmagenta:8B008B,darkolivegreen:556B2F,darkorange:FF8C00,darkorchid:9932CC,darkred:8B0000,' +
    'darksalmon:E9967A,darkseagreen:8FBC8F,darkslateblue:483D8B,darkslategray:2F4F4F,' +
    'darkslategrey:2F4F4F,darkturquoise:00CED1,darkviolet:9400D3,deeppink:FF1493,deepskyblue:00BFFF,' +
    'dimgray:696969,dimgrey:696969,dodgerblue:1E90FF,firebrick:B22222,floralwhite:FFFAF0,' +
    'forestgreen:228B22,fuchsia:FF00FF,gainsboro:DCDCDC,ghostwhite:F8F8FF,gold:FFD700,goldenrod:DAA520,' +
    'gray:808080,green:008000,greenyellow:ADFF2F,grey:808080,honeydew:F0FFF0,hotpink:FF69B4,' +
    'indianred:CD5C5C,indigo:4B0082,ivory:FFFFF0,khaki:F0E68C,lavender:E6E6FA,lavenderblush:FFF0F5,' +
    'lawngreen:7CFC00,lemonchiffon:FFFACD,lightblue:ADD8E6,lightcoral:F08080,lightcyan:E0FFFF,' +
    'lightgoldenrodyellow:FAFAD2,lightgray:D3D3D3,lightgreen:90EE90,lightgrey:D3D3D3,lightpink:FFB6C1,' +
    'lightsalmon:FFA07A,lightseagreen:20B2AA,lightskyblue:87CEFA,lightslategray:778899,' +
    'lightslategrey:778899,lightsteelblue:B0C4DE,lightyellow:FFFFE0,lime:00FF00,limegreen:32CD32,' +
    'linen:FAF0E6,magenta:FF00FF,maroon:800000,mediumaquamarine:66CDAA,mediumblue:0000CD,' +
    'mediumorchid:BA55D3,mediumpurple:9370DB,mediumseagreen:3CB371,mediumslateblue:7B68EE,' +
    'mediumspringgreen:00FA9A,mediumturquoise:48D1CC,mediumvioletred:C71585,midnightblue:191970,' +
    'mintcream:F5FFFA,mistyrose:FFE4E1,moccasin:FFE4B5,navajowhite:FFDEAD,navy:000080,oldlace:FDF5E6,' +
    'olive:808000,olivedrab:6B8E23,orange:FFA500,orangered:FF4500,orchid:DA70D6,palegoldenrod:EEE8AA,' +
    'palegreen:98FB98,paleturquoise:AFEEEE,palevioletred:DB7093,papayawhip:FFEFD5,peachpuff:FFDAB9,' +
    'peru:CD853F,pink:FFC0CB,plum:DDA0DD,powderblue:B0E0E6,purple:800080,rebeccapurple:663399,red:FF0000,' +
    'rosybrown:BC8F8F,royalblue:4169E1,saddlebrown:8B4513,salmon:FA8072,sandybrown:F4A460,' +
    'seagreen:2E8B57,seashell:FFF5EE,sienna:A0522D,silver:C0C0C0,skyblue:87CEEB,slateblue:6A5ACD,' +
    'slategray:708090,slategrey:708090,snow:FFFAFA,springgreen:00FF7F,steelblue:4682B4,tan:D2B48C,' +
    'teal:008080,thistle:D8BFD8,tomato:FF6347,turquoise:40E0D0,violet:EE82EE,wheat:F5DEB3,white:FFFFFF,' +
    'whitesmoke:F5F5F5,yellow:FFFF00,yellowgreen:9ACD32'
  )
    .split(',')
    .map((e) => {
      const [name, hex] = e.split(':');
      return [name, '#' + hex];
    }),
);

// Python's str whitespace and \w, so \s, \S and \w mean what they mean in tokenize.py.
const WS = '\\t\\n\\v\\f\\r\\x1c-\\x1f \\x85\\xa0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000';
const S = `[${WS}]`;
const NS = `[^${WS}]`;
const W = '\\p{L}\\p{N}_';

// A comment, or a start, end or empty-element tag with quoted attribute values (which may hold '>').
const TAG = new RegExp(
  `<!--.*?-->|<(?<end>/?)(?<name>[A-Za-z][${W}:.-]*)(?<attrs>(?:${S}+[^${WS}=/>"']+${S}*=${S}*(?:"[^"]*"|'[^']*'))*)${S}*(?<empty>/?)>`,
  'gsu',
);
const ATTR = new RegExp(`([^${WS}=/>"']+)${S}*=${S}*(?:"([^"]*)"|'([^']*)')`, 'gu');
const DECL = new RegExp(`(?<![${W}-])(${PAINT.join('|')})${S}*:([^;{}]*)`, 'gu');
const LEAD = new RegExp(`^${S}*`, 'u');
const ATTR_VALUE = new RegExp(`^${S}*(${NS}+?)${S}*$`, 'u');
const CSS_VALUE = new RegExp(`^${S}*(${NS}+?)${S}*(?:!${S}*important${S}*)?$`, 'iu');
const HEX = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;
const STYLE_END = new RegExp(`</style${S}*>`, 'gu');

/** Uppercase #RRGGBB for a hex3/hex6/named colour, else null. */
function colour(value: string): string | null {
  if (HEX.test(value)) {
    const h = value.slice(1);
    return '#' + (h.length === 6 ? h : h.replace(/./g, '$&$&')).toUpperCase();
  }
  return NAMED.get(value.toLowerCase()) ?? null;
}

function match(out: Slot[], text: string, offset: number, valueRe: RegExp): void {
  const m = valueRe.exec(text);
  const c = m && colour(m[1]);
  if (c) {
    // The leading \s* is greedy and group 1 cannot start with whitespace, so the group starts after it.
    const start = offset + (LEAD.exec(text) as RegExpExecArray)[0].length;
    out.push([start, start + m[1].length, c]);
  }
}

function css(out: Slot[], text: string, offset: number): void {
  for (const d of text.matchAll(DECL)) match(out, d[2], offset + d.index + d[0].length - d[2].length, CSS_VALUE);
}

/** Every slot in `svg`, sorted by start. */
export function findColours(svg: string): Slot[] {
  const out: Slot[] = [];
  let pos = 0;
  for (;;) {
    TAG.lastIndex = pos;
    const m = TAG.exec(svg);
    if (!m) break;
    pos = m.index + m[0].length;
    const { end, name, attrs, empty } = m.groups as Record<string, string | undefined>;
    if (!name || end) continue;
    const base = m.index + 1 + name.length;
    for (const a of (attrs as string).matchAll(ATTR)) {
      const value = a[2] ?? (a[3] as string);
      // The match ends with the value's closing quote.
      const start = base + a.index + a[0].length - 1 - value.length;
      if (a[1] === 'style') css(out, value, start);
      else if ((PAINT as readonly string[]).includes(a[1])) match(out, value, start, ATTR_VALUE);
    }
    if (name === 'style' && !empty) {
      STYLE_END.lastIndex = pos;
      const close = STYLE_END.exec(svg);
      const stop = close ? close.index : svg.length;
      css(out, svg.slice(pos, stop), pos);
      pos = stop;
    }
  }
  return out;
}

/** The text around the slots of `svg`: slots.length + 1 pieces, so joining them with one value per slot rebuilds it. */
export function splitSlots(svg: string, slots: Slot[] = findColours(svg)): string[] {
  const parts: string[] = [];
  let last = 0;
  for (const [start, end] of slots) {
    parts.push(svg.slice(last, start));
    last = end;
  }
  parts.push(svg.slice(last));
  return parts;
}

/** `parts` (from splitSlots) joined with values[i] in slot i; throws unless there is one value per slot. */
export function joinSlots(parts: readonly string[], values: readonly string[]): string {
  if (values.length !== parts.length - 1) throw new Error(`${values.length} values for ${parts.length - 1} colour slots`);
  let out = parts[0];
  for (let i = 0; i < values.length; i++) out += values[i] + parts[i + 1];
  return out;
}

/** `svg` with slot i replaced by values[i]; throws unless there is one value per slot. */
export function substitute(svg: string, values: readonly string[]): string {
  return joinSlots(splitSlots(svg), values);
}

/** `svg` with every slot rewritten to uppercase #RRGGBB; idempotent, pixels unchanged. */
export function normalise(svg: string): string {
  const slots = findColours(svg);
  return joinSlots(splitSlots(svg, slots), slots.map((s) => s[2]));
}

/** `svg` with every slot replaced by SKELETON_MARK: equal skeletons mean equal geometry and slot positions. */
export function skeleton(svg: string): string {
  const parts = splitSlots(svg);
  return parts.join(SKELETON_MARK);
}
