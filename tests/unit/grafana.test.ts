import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { CHARTED, OTHER } from '../../scripts/stats/events';
import { BLOBS, DOUBLES } from '../../src/lib/events';

interface Target {
  datasource: { type: string; uid: string };
  editorMode?: string;
  query?: string;
  root_selector?: string;
  summarizeBy?: string;
  url?: string;
}
interface Panel {
  type: string;
  title: string;
  datasource?: Target['datasource'];
  targets?: Target[];
}

const dashboard = JSON.parse(readFileSync('infra/grafana/walldye.json', 'utf8')) as {
  __inputs: { name: string; pluginId: string }[];
  panels: Panel[];
};
const targets = dashboard.panels.flatMap((p) => p.targets ?? []);
const sql = targets.filter((t) => t.datasource.type === 'vertamedia-clickhouse-datasource');
const infinity = targets.filter((t) => t.datasource.type === 'yesoreyeram-infinity-datasource');

describe('infra/grafana/walldye.json', () => {
  it('names every blob and double where it reads it, after the field the row layout puts there', () => {
    let aliases = 0;
    for (const { query } of sql) {
      for (const m of query!.matchAll(/\b(blob|double)(\d+)\b/gi)) {
        const layout = m[1].toLowerCase() === 'blob' ? BLOBS : DOUBLES;
        const alias = /^\s+AS\s+(\w+)/i.exec(query!.slice(m.index + m[0].length))?.[1];
        expect(alias, `${m[0]} in ${query}`).toBe(layout[Number(m[2]) - 1]);
        aliases++;
      }
    }
    expect(aliases).toBeGreaterThan(20);
  });

  it('reads only the production dataset, weighting counts by sampling', () => {
    expect(sql.length).toBeGreaterThan(0);
    for (const { query } of sql) {
      expect(query).toMatch(/\bFROM walldye_events WHERE \$timeFilter\b/);
      expect(query).not.toMatch(/\bcount\(\)/);
    }
  });

  it('opens its Analytics Engine queries in the SQL editor', () => {
    for (const t of sql) expect(t.editorMode, t.query).toBe('sql');
  });

  it('reads all.json from the stats branch, for fields all.json counts', () => {
    expect(infinity.length).toBeGreaterThan(0);
    for (const t of infinity) {
      expect(t.url).toBe(
        'https://raw.githubusercontent.com/nickolaj-jepsen/walldye/stats/events/all.json',
      );
      for (const [, event, field] of t.root_selector!.matchAll(
        /event = '(\w+)' and field = '(\w+)'/g,
      )) {
        const charted =
          event === 'downloads' ? ['slug'] : (CHARTED as Record<string, readonly string[]>)[event];
        expect(charted, `${event}.${field}`).toContain(field);
      }
      if (t.summarizeBy) expect(t.root_selector).toContain(`value != '${OTHER}'`);
    }
  });

  it('takes both data sources as import inputs', () => {
    const inputs = new Map(dashboard.__inputs.map((i) => [`\${${i.name}}`, i.pluginId]));
    for (const p of dashboard.panels.filter((p) => p.type !== 'row')) {
      for (const ds of [p.datasource!, ...p.targets!.map((t) => t.datasource)])
        expect(inputs.get(ds.uid), p.title).toBe(ds.type);
    }
  });
});
