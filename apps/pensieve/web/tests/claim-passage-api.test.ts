import assert from "node:assert/strict";
import { test } from "node:test";
import { spawnSync } from "node:child_process";
import { setImmediate } from "node:timers/promises";
import { lookupClaimPassages } from "../src/server/claim-passage-api.ts";
import type { ClaimPassageResponse } from "../src/claim-passages/claim-passage-contract.ts";

function claim() { return { kind: "sourced_lore", statement: "A lantern arrives.", sources: [{ source_id: "synthetic-atlas", title: "The Folded Lantern Atlas", canon_tier: "book", locator: { kind: "chapter", reference: "A" } }] }; }
function body(): ClaimPassageResponse { const c = claim(); return { statement: c.statement, references: [{ reference: c.sources[0] as ClaimPassageResponse["references"][number]["reference"], status: "REGISTRY_MATCH", passages: [] }], all_references_registered: true, all_references_have_passages: false }; }
const local = { origin: "http://127.0.0.1:8000" };
const json = (value: unknown = body(), status = 200) => Response.json(value, { status });

test("malformed UTF-16 in any request text, including a final citation, makes zero fetch calls", async () => {
  let calls = 0;
  const fetcher: typeof fetch = async () => { calls++; return json(); };
  for (const value of ["\ud800", "\udfff", "before\ud800after", "before\udfffafter"]) {
    const reference = claim().sources[0];
    const invalid = [
      { ...claim(), statement: value },
      ...["source_id", "title"].flatMap(key => [
        { ...claim(), sources: [{ ...reference, [key]: value }] },
        { ...claim(), sources: [reference, { ...reference, [key]: value }] },
      ]),
      ...[0, 1].map(index => ({ ...claim(), sources: [reference, reference].map((r, i) => i === index ? { ...r, locator: { ...r.locator, reference: value } } : r) })),
    ];
    for (const c of invalid) assert.deepEqual(await lookupClaimPassages(c, { ...local, fetcher }), { status: "invalid_request" });
  }
  assert.equal(calls, 0);
});

test("malformed response passage IDs and text return only unavailable", async () => {
  for (const value of ["\ud800", "\udfff", "before\ud800after", "before\udfffafter"]) {
    for (const key of ["passage_id", "text"] as const) {
      const r = body();
      const passage = { kind: "source_passage" as const, passage_id: "arrival", reference: r.references[0].reference, text: "Original synthetic text." };
      passage[key] = value; r.references[0].passages = [passage]; r.all_references_have_passages = true;
      assert.deepEqual(await lookupClaimPassages(claim(), { ...local, fetcher: async () => json(r) }), { status: "unavailable" });
    }
  }
});

test("valid supplementary pairs survive request serialization and validated responses", async () => {
  const value = "before\u{1f680}\u{10000}after";
  const c = claim(); c.statement = value;
  Object.assign(c.sources[0], { source_id: value, title: value }); c.sources[0].locator.reference = value;
  const r = body(); r.statement = value;
  Object.assign(r.references[0].reference, c.sources[0]);
  r.references[0].passages = [{ kind: "source_passage", passage_id: value, reference: structuredClone(r.references[0].reference), text: value }];
  r.all_references_have_passages = true;
  let calls = 0;
  assert.deepEqual(await lookupClaimPassages(c, { ...local, fetcher: async (_, init) => {
    calls++; assert.deepEqual(JSON.parse(init?.body as string), c); return json(r);
  } }), { status: "ok", data: r });
  assert.equal(calls, 1);
});

test("import makes no network request", () => {
  const url = new URL("../src/server/claim-passage-api.ts", import.meta.url).href;
  const result = spawnSync(process.execPath, ["--experimental-strip-types", "--input-type=module", "-e", `globalThis.fetch = () => { process.exit(7); }; await import(${JSON.stringify(url)});`], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr);
});

test("exact fixed POST and normalized body; owned serialization precedes asynchronous work", async () => {
  for (const origin of ["http://127.0.0.1:8000", "http://localhost/", "https://example.test:8443/", "HTTPS://example.test", "http://[::1]:8100"]) {
    const c = claim(); c.statement = "\u0085 " + c.statement + "\u00a0"; c.sources[0].title = " " + c.sources[0].title;
    let calls = 0;
    const pending = lookupClaimPassages(c, { origin, fetcher: async (url, init) => {
      calls++; assert.equal(String(url), new URL("/api/v1/claims/passages/lookup", origin).href);
      assert.equal(init?.method, "POST"); assert.deepEqual(init?.headers, { Accept: "application/json", "Content-Type": "application/json" });
      assert.deepEqual(JSON.parse(init?.body as string), claim());
      assert.equal(init?.cache, "no-store"); assert.equal(init?.redirect, "error"); assert.ok(init?.signal instanceof AbortSignal);
      await setImmediate(); return json();
    } });
    c.statement = "changed"; c.sources[0].locator.reference = "changed";
    assert.deepEqual(await pending, { status: "ok", data: body() }); assert.equal(calls, 1);
  }
});

test("invalid entire request takes priority over invalid configuration and never fetches", async () => {
  for (const value of [null, {}, { ...claim(), kind: "generated_roleplay" }, { ...claim(), sources: [...claim().sources, { ...claim().sources[0], title: null }] }]) {
    let calls = 0;
    assert.deepEqual(await lookupClaimPassages(value, { origin: "", fetcher: async () => { calls++; return json(); } }), { status: "invalid_request" });
    assert.equal(calls, 0);
  }
});

test("reads origin at call time and defaults only for absent environment", async t => {
  const previous = process.env.PENSIEVE_API_ORIGIN;
  t.after(() => { if (previous === undefined) delete process.env.PENSIEVE_API_ORIGIN; else process.env.PENSIEVE_API_ORIGIN = previous; });
  const seen: string[] = []; const fetcher: typeof fetch = async url => { seen.push(String(url)); return json(); };
  delete process.env.PENSIEVE_API_ORIGIN;
  assert.equal((await lookupClaimPassages(claim(), { fetcher })).status, "ok");
  process.env.PENSIEVE_API_ORIGIN = "https://example.test:8443/";
  assert.equal((await lookupClaimPassages(claim(), { fetcher })).status, "ok");
  process.env.PENSIEVE_API_ORIGIN = "";
  assert.deepEqual(await lookupClaimPassages(claim(), { fetcher }), { status: "unavailable" });
  assert.deepEqual(seen, ["http://127.0.0.1:8000/api/v1/claims/passages/lookup", "https://example.test:8443/api/v1/claims/passages/lookup"]);
});

test("rejects all health-boundary invalid origins without network activity", async () => {
  for (const origin of ["", " ", "nonsense", "//example.test", "ftp://example.test", "http:example.test", "https:///example.test", "https://user:secret@example.test", "https://@example.test", "https://example.test?", "https://example.test?q=private", "https://example.test#", "https://example.test#private", "https://example.test/prefix", "https://example.test/prefix/..", "https://example.test/./", "https://example.test//", " https://example.test", "https://exam\tple.test", "https://example.test\n", "https://example.test\\prefix", "https://example.test:99999"]) {
    let calls = 0;
    assert.deepEqual(await lookupClaimPassages(claim(), { origin, fetcher: async () => { calls++; return json(); } }), { status: "unavailable" }, origin);
    assert.equal(calls, 0);
  }
});

test("only exact known JSON 503 is not_configured; other statuses and private bodies are bounded", async t => {
  const log = t.mock.method(console, "log"); const error = t.mock.method(console, "error");
  const known = { detail: "Passage lookup is not configured" };
  assert.deepEqual(await lookupClaimPassages(claim(), { ...local, fetcher: async () => json(known, 503) }), { status: "not_configured" });
  for (const value of [null, [], "SYNTHETIC_PRIVATE", {}, { detail: "SYNTHETIC_PRIVATE" }, { ...known, private: "SYNTHETIC_PRIVATE" }]) {
    assert.deepEqual(await lookupClaimPassages(claim(), { ...local, fetcher: async () => json(value, 503) }), { status: "unavailable" });
  }
  for (const status of [201, 204, 301, 302, 400, 401, 422, 500, 504]) assert.deepEqual(await lookupClaimPassages(claim(), { ...local, fetcher: async () => new Response(null, { status }) }), { status: "unavailable" });
  assert.equal(log.mock.callCount(), 0); assert.equal(error.mock.callCount(), 0);
});

test("JSON content type, redirects, malformed JSON and primitive data fail closed", async () => {
  for (const status of [200, 503]) {
    const value = status === 200 ? body() : { detail: "Passage lookup is not configured" };
    for (const ct of [null, "text/plain", "application/problem+json", "application/json-fake", "text/application/json"]) {
      assert.deepEqual(await lookupClaimPassages(claim(), { ...local, fetcher: async () => new Response(JSON.stringify(value), { status, headers: ct ? { "Content-Type": ct } : {} }) }), { status: "unavailable" });
    }
    for (const ct of ["application/json", "Application/JSON; Charset=UTF-8", "application/json ; charset=utf-8"]) {
      assert.equal((await lookupClaimPassages(claim(), { ...local, fetcher: async () => new Response(JSON.stringify(value), { status, headers: { "Content-Type": ct } }) })).status, status === 200 ? "ok" : "not_configured");
    }
    assert.deepEqual(await lookupClaimPassages(claim(), { ...local, fetcher: async () => new Response("SYNTHETIC_PRIVATE_BAD_JSON", { status, headers: { "Content-Type": "application/json" } }) }), { status: "unavailable" });
    const redirected = json(value, status); Object.defineProperty(redirected, "redirected", { value: true });
    assert.deepEqual(await lookupClaimPassages(claim(), { ...local, fetcher: async () => redirected }), { status: "unavailable" });
  }
  for (const value of [null, [], 1, false, "wire"]) assert.deepEqual(await lookupClaimPassages(claim(), { ...local, fetcher: async () => json(value) }), { status: "unavailable" });
});

test("client rejects request binding, normalized wire and domain invariant failures", async () => {
  const mutations: ((r: ClaimPassageResponse) => void)[] = [
    r => { r.statement += "!"; }, r => { r.references = []; }, r => { r.references.push(structuredClone(r.references[0])); },
    r => { r.references[0].reference.title += "!"; }, r => { r.references[0].reference.locator.reference = "B"; },
    r => { r.references[0].status = "SOURCE_METADATA_MISMATCH"; }, r => { r.all_references_registered = false; },
    r => { r.all_references_have_passages = true; }, r => { r.statement = " " + r.statement; },
    r => { Object.assign(r, { private: "SYNTHETIC_PRIVATE" }); },
    r => { r.references[0].passages = [{ kind: "source_passage", passage_id: "a", reference: { ...r.references[0].reference, title: "wrong" }, text: "original" }]; r.all_references_have_passages = true; },
    r => { const p = { kind: "source_passage" as const, passage_id: "a", reference: r.references[0].reference, text: "original" }; r.references[0].passages = [p, p]; r.all_references_have_passages = true; },
  ];
  for (const mutate of mutations) { const r = body(); mutate(r); assert.deepEqual(await lookupClaimPassages(claim(), { ...local, fetcher: async () => json(r) }), { status: "unavailable" }); }
});

test("fetch and body exceptions expose no error details or logs", async t => {
  const log = t.mock.method(console, "log"); const error = t.mock.method(console, "error");
  for (const phase of ["fetch", "body"]) {
    assert.deepEqual(await lookupClaimPassages(claim(), { ...local, fetcher: async () => {
      if (phase === "fetch") throw new Error("SYNTHETIC_PRIVATE_TRANSPORT");
      const r = json(); r.json = async () => { throw new Error("SYNTHETIC_PRIVATE_BODY"); }; return r;
    } }), { status: "unavailable" });
  }
  assert.equal(log.mock.callCount(), 0); assert.equal(error.mock.callCount(), 0);
});

for (const phase of ["fetch", "body", "503-body"] as const) for (const aware of [false, true]) {
  test(`deadline bounds ${phase}, abort aware=${aware}, and cleans timer`, async t => {
    t.mock.timers.enable({ apis: ["setTimeout"] }); const cleared = t.mock.method(globalThis, "clearTimeout");
    let signal: AbortSignal | undefined; let reading = false;
    const pending = lookupClaimPassages(claim(), { ...local, fetcher: async (_, init) => {
      signal = init?.signal as AbortSignal;
      const hang = <T>() => new Promise<T>((_, reject) => { if (aware) signal!.addEventListener("abort", () => reject(new Error("SYNTHETIC_PRIVATE_ABORT")), { once: true }); });
      if (phase === "fetch") return hang<Response>();
      const r = json(undefined, phase === "503-body" ? 503 : 200);
      r.json = () => { reading = true; return hang(); }; return r;
    } });
    await setImmediate(); assert.equal(reading, phase !== "fetch");
    t.mock.timers.tick(2999); assert.equal(signal?.aborted, false);
    t.mock.timers.tick(1); assert.deepEqual(await pending, { status: "unavailable" });
    assert.equal(signal?.aborted, true); assert.equal(cleared.mock.callCount(), 1);
  });
}

test("custom deadline and fresh calls clear timers for every completion path", async t => {
  t.mock.timers.enable({ apis: ["setTimeout"] }); const cleared = t.mock.method(globalThis, "clearTimeout");
  const signals: AbortSignal[] = []; let calls = 0;
  const fetcher: typeof fetch = async (_, init) => { signals.push(init?.signal as AbortSignal); calls++; return calls === 2 ? json({ detail: "Passage lookup is not configured" }, 503) : calls === 3 ? json({ private: "SYNTHETIC_PRIVATE" }) : json(); };
  for (const status of ["ok", "not_configured", "unavailable", "ok"]) assert.equal((await lookupClaimPassages(claim(), { ...local, fetcher })).status, status);
  assert.equal(cleared.mock.callCount(), 4); t.mock.timers.tick(5000); assert.ok(signals.every(s => !s.aborted));
  const pending = lookupClaimPassages(claim(), { ...local, timeoutMs: 7, fetcher: async () => new Promise(() => {}) });
  t.mock.timers.tick(7); assert.deepEqual(await pending, { status: "unavailable" });
});
