import { parse } from 'yaml';

/**
 * `text` parsed the way the Python tools' PyYAML safe_load reads it: YAML 1.1, so `yes` and `no`
 * are booleans and a repeated key keeps its last value. Dates stay text, as the schema wants them.
 */
export function parseYaml(text: string): unknown {
  return parse(text, {
    version: '1.1',
    uniqueKeys: false,
    customTags: (tags) =>
      tags.filter((t) => typeof t !== 'object' || t.tag !== 'tag:yaml.org,2002:timestamp'),
  });
}
