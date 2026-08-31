/**
 * A Node harness for the Durable Object in ../../durable.ts.
 *
 * WHY THIS EXISTS. service/'s suite runs under `node --test`, not under
 * workerd, so `DurableObjectState.storage.sql` does not exist here. This file
 * supplies the smallest thing `PumasiSignService` actually consumes: a
 * `SqlStorage`-shaped object backed by node:sqlite's in-memory DatabaseSync,
 * and a fake `DurableObjectState` carrying it.
 *
 * WHAT IT DOES NOT CLAIM. This is SQLite, but it is not workerd's SQLite, and
 * a test written against it records the behaviour of durable.ts's own logic
 * rather than the behaviour of the deployment byte for byte. Where the two
 * could differ -- value coercion at the storage boundary, statement limits --
 * a test here is evidence about the code, not about Cloudflare. That is stated
 * so a reader does not over-read a green count, which is the whole failure
 * pumasi/lessons/L-006 names.
 *
 * node:sqlite is imported unconditionally and deliberately NOT guarded with a
 * skip: if it ever stops being available, every test that needs it must go
 * red rather than quietly pass having run nothing.
 */

import { DatabaseSync } from 'node:sqlite';
import { PumasiSignService, Env } from '../../durable.js';

/**
 * `sql.exec` in workerd takes one or more statements and returns a cursor that
 * is iterable over row objects. node:sqlite splits those two jobs: `exec` runs
 * statements and returns nothing, `prepare(...).all(...)` runs one statement
 * and returns rows. This bridges them.
 */
function sqlStorage(db: DatabaseSync) {
  return {
    exec(query: string, ...bindings: unknown[]): any {
      // A statement that returns rows must go through `prepare(...).all(...)`;
      // everything else through `exec`, which is the only one of the two that
      // accepts the multi-statement block initSchema passes. The order matters:
      // node:sqlite's `prepare` does NOT reject a multi-statement string, it
      // silently keeps the first statement -- measured, and it is why this is
      // a shape test rather than a try/catch.
      if (/^\s*(SELECT|WITH|PRAGMA)\b/i.test(query) || /\bRETURNING\b/i.test(query)) {
        return cursor(db.prepare(query).all(...(bindings as any[])) as unknown[]);
      }
      if (bindings.length === 0) {
        db.exec(query);
        return cursor([]);
      }
      db.prepare(query).run(...(bindings as any[]));
      return cursor([]);
    },
  };
}

function cursor(rows: unknown[]) {
  return {
    toArray: () => rows,
    one: () => rows[0],
    raw: () => rows[Symbol.iterator](),
    [Symbol.iterator]: () => rows[Symbol.iterator](),
    columnNames: rows.length ? Object.keys(rows[0] as object) : [],
    rowsRead: rows.length,
    rowsWritten: 0,
  };
}

export interface Harness {
  service: PumasiSignService;
  /** The same database the service writes to -- for seeding and for reading back. */
  db: DatabaseSync;
  /** Drive the Durable Object exactly as worker.ts does: through fetch(). */
  fetch(path: string, init?: RequestInit & { cookie?: string }): Promise<Response>;
}

export function newHarness(env: Partial<Env> = {}): Harness {
  const db = new DatabaseSync(':memory:');
  const state = { storage: { sql: sqlStorage(db) } };
  const service = new PumasiSignService(
    state as unknown as DurableObjectState,
    { BASE_URL: 'https://sign.example.test', ...env } as Env,
  );
  return {
    service,
    db,
    fetch(path, init = {}) {
      const { cookie, headers, ...rest } = init;
      const h = new Headers(headers as HeadersInit | undefined);
      if (cookie) h.set('cookie', cookie);
      if (rest.body && !h.has('content-type')) h.set('content-type', 'application/json');
      return service.fetch(new Request(`https://sign.example.test${path}`, { ...rest, headers: h }));
    },
  };
}

/** The value a Set-Cookie header assigns to `name`, or undefined. */
export function cookieValue(res: Response, name: string): string | undefined {
  for (const raw of res.headers.getSetCookie()) {
    const [pair] = raw.split(';');
    const eq = pair.indexOf('=');
    if (eq > 0 && pair.slice(0, eq).trim() === name) return pair.slice(eq + 1);
  }
  return undefined;
}
