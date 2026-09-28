/**
 * Writes `<dir>/<YYYY-MM-DD>.json`, walldye.com's page views by slug, for every complete UTC day
 * that Cloudflare Web Analytics still holds and `dir` has no file for.
 *
 * node scripts/views/fetch.ts <dir>
 *
 * Reads CLOUDFLARE_ANALYTICS_TOKEN (Account Analytics Read) and CLOUDFLARE_ACCOUNT_ID.
 */
import { mkdirSync, readdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { DAY_FILE, dayNumber, isoDay, pathSlug, type Day } from '../../src/lib/views.ts';

const API = 'https://api.cloudflare.com/client/v4/graphql';
const HOST = 'walldye.com';

export interface Limits {
  /** Seconds back from now that the dataset reaches. */
  notOlderThan: number;
  /** Widest time range one query may span, in seconds. */
  maxDuration: number;
  maxPageSize: number;
}

export interface Row {
  count: number;
  dimensions: { date: string; requestPath: string };
}

/**
 * Day numbers to fetch, oldest first: from the day after the newest file (or the oldest whole day
 * within `notOlderThan` when there is none) up to yesterday.
 */
export function daysToFetch(have: readonly string[], now: Date, notOlderThan: number): number[] {
  const today = Math.floor(now.getTime() / 86_400_000);
  const oldest = Math.ceil((now.getTime() / 1000 - notOlderThan) / 86_400);
  const newest = have.length ? Math.max(...have.map(dayNumber)) : oldest - 1;
  const out: number[] = [];
  for (let d = Math.max(newest + 1, oldest); d < today; d++) out.push(d);
  return out;
}

/** Consecutive `days` in runs of at most `maxDays`. */
export function chunks(days: readonly number[], maxDays: number): number[][] {
  const out: number[][] = [];
  for (const d of days) {
    const last = out.at(-1);
    if (last && d === last.at(-1)! + 1 && last.length < maxDays) last.push(d);
    else out.push([d]);
  }
  return out;
}

/**
 * The rows as one Day per requested day, paths that name no slug dropped and `/x/` merged into `/x`.
 * Before the first day with a view, days are left out when `fresh`, so a run that finds nothing
 * records nothing and a later run starts over.
 */
export function toDays(rows: readonly Row[], days: readonly number[], fresh: boolean): Map<string, Day> {
  const out = new Map<string, Day>(days.map((d) => [isoDay(d), {}]));
  for (const { count, dimensions } of rows) {
    const slug = pathSlug(dimensions.requestPath);
    const day = out.get(dimensions.date);
    if (!slug || !day) continue;
    day[slug] = (day[slug] ?? 0) + count;
  }
  if (fresh) {
    for (const [date, day] of out) {
      if (Object.keys(day).length) break;
      out.delete(date);
    }
  }
  return out;
}

/** `day` with its slugs sorted, one per line. */
export function dayJson(day: Day): string {
  const sorted = Object.fromEntries(Object.entries(day).sort(([a], [b]) => (a < b ? -1 : 1)));
  return `${JSON.stringify(sorted, null, 2)}\n`;
}

async function query<T>(token: string, text: string, variables: Record<string, unknown>): Promise<T> {
  const res = await fetch(API, {
    method: 'POST',
    headers: { authorization: `Bearer ${token}`, 'content-type': 'application/json' },
    body: JSON.stringify({ query: text, variables }),
  });
  const body = (await res.json().catch(() => ({}))) as { data?: T; errors?: { message: string }[] | null };
  if (!res.ok || body.errors?.length || !body.data) {
    throw new Error(`Cloudflare GraphQL ${res.status}: ${body.errors?.map((e) => e.message).join('; ') ?? res.statusText}`);
  }
  return body.data;
}

type Accounts<T> = { viewer: { accounts: T[] } };

async function limits(token: string, account: string): Promise<Limits> {
  const data = await query<Accounts<{ settings: { rumPageloadEventsAdaptiveGroups: (Limits & { enabled: boolean }) | null } }>>(
    token,
    `query ($account: string!) {
      viewer { accounts(filter: { accountTag: $account }) { settings {
        rumPageloadEventsAdaptiveGroups { enabled notOlderThan maxDuration maxPageSize }
      } } }
    }`,
    { account },
  );
  const s = data.viewer.accounts[0]?.settings.rumPageloadEventsAdaptiveGroups;
  if (!s?.enabled) throw new Error(`account ${account} cannot read rumPageloadEventsAdaptiveGroups`);
  return s;
}

async function rows(token: string, account: string, days: readonly number[], pageSize: number): Promise<Row[]> {
  const data = await query<Accounts<{ rumPageloadEventsAdaptiveGroups: Row[] }>>(
    token,
    `query ($account: string!, $host: string!, $start: Time!, $end: Time!) {
      viewer { accounts(filter: { accountTag: $account }) {
        rumPageloadEventsAdaptiveGroups(
          limit: ${pageSize}
          filter: { requestHost: $host, datetime_geq: $start, datetime_lt: $end }
        ) { count dimensions { date requestPath } }
      } }
    }`,
    {
      account,
      host: HOST,
      start: new Date(days[0] * 86_400_000).toISOString(),
      end: new Date((days.at(-1)! + 1) * 86_400_000).toISOString(),
    },
  );
  const out = data.viewer.accounts[0]?.rumPageloadEventsAdaptiveGroups ?? [];
  // The limit truncates without an error.
  if (out.length >= pageSize) throw new Error(`${isoDay(days[0])}..${isoDay(days.at(-1)!)}: ${out.length} groups hit the page size`);
  return out;
}

function env(name: string): string {
  const v = process.env[name]?.trim();
  if (!v) throw new Error(`${name} is not set`);
  return v;
}

async function main(dir: string | undefined): Promise<void> {
  if (!dir) throw new Error('usage: node scripts/views/fetch.ts <dir>');
  const token = env('CLOUDFLARE_ANALYTICS_TOKEN');
  const account = env('CLOUDFLARE_ACCOUNT_ID');
  mkdirSync(dir, { recursive: true });
  const have = readdirSync(dir).flatMap((f) => DAY_FILE.exec(f)?.[1] ?? []);

  const lim = await limits(token, account);
  const days = daysToFetch(have, new Date(), lim.notOlderThan);
  if (!days.length) return console.log('nothing to fetch');
  // Whole days only: a range ends at the next midnight, so maxDuration counts the days it spans.
  const perQuery = Math.max(1, Math.floor(lim.maxDuration / 86_400));
  for (const run of chunks(days, perQuery)) {
    const found = toDays(await rows(token, account, run, lim.maxPageSize), run, have.length === 0);
    for (const [date, day] of found) {
      writeFileSync(join(dir, `${date}.json`), dayJson(day));
      have.push(date);
      console.log(`${date}: ${Object.values(day).reduce((a, b) => a + b, 0)} views`);
    }
  }
}

if (import.meta.main) {
  main(process.argv[2]).catch((e: Error) => {
    console.error(e.message);
    process.exit(1);
  });
}
