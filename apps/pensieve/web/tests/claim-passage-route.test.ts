import assert from "node:assert/strict";
import { test } from "node:test";
import { POST, runtime } from "../src/app/api/claims/passages/lookup/route.ts";

function claim() { return { kind: "sourced_lore", statement: "A fictional lantern arrives.", sources: [{ source_id: "synthetic-atlas", title: "The Folded Lantern Atlas", canon_tier: "book", locator: { kind: "chapter", reference: "A" } }] }; }
function request(value: unknown = claim(), contentType: string | null = "application/json") {
  return new Request("http://web.test/api/claims/passages/lookup?origin=https://private.test&secret=SYNTHETIC_PRIVATE", { method: "POST", headers: { ...(contentType ? { "Content-Type": contentType } : {}), Cookie: "SYNTHETIC_PRIVATE", Authorization: "SYNTHETIC_PRIVATE", "X-Private": "SYNTHETIC_PRIVATE" }, body: JSON.stringify(value) });
}
async function check(response: Response, status: number, body: unknown) {
  assert.equal(response.status, status); assert.equal(response.headers.get("cache-control"), "no-store");
  assert.equal(response.headers.get("content-type"), "application/json"); assert.deepEqual(await response.json(), body);
  assert.equal(response.headers.get("x-private"), null);
}

test("escaped unpaired surrogates in valid JSON return 400 with zero upstream calls", async t => {
  let calls = 0;
  t.mock.method(globalThis, "fetch", async () => { calls++; throw new Error("Unexpected upstream request"); });
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
    for (const c of invalid) {
      // request() uses JSON.stringify, preserving escaped surrogates through BodyInit encoding.
      const req = request(c);
      const wire = await req.clone().text();
      assert.ok(wire.includes("\\ud800") || wire.includes("\\udfff"));
      assert.deepEqual(JSON.parse(wire), c);
      await check(await POST(req), 400, { error: "INVALID_CLAIM" });
    }
  }
  assert.equal(calls, 0);
});

test("actual POST preserves valid supplementary pairs in claims and passage text", async t => {
  const previous = process.env.PENSIEVE_API_ORIGIN;
  t.after(() => { if (previous === undefined) delete process.env.PENSIEVE_API_ORIGIN; else process.env.PENSIEVE_API_ORIGIN = previous; });
  process.env.PENSIEVE_API_ORIGIN = "http://backend.test:8100";
  const value = "before\u{1f680}\u{10000}after";
  const c = claim(); c.statement = value;
  Object.assign(c.sources[0], { source_id: value, title: value }); c.sources[0].locator.reference = value;
  const reference = c.sources[0];
  const expected = { statement: value, references: [{ reference, status: "REGISTRY_MATCH", passages: [{ kind: "source_passage", passage_id: value, reference, text: value }] }], all_references_registered: true, all_references_have_passages: true };
  let calls = 0;
  t.mock.method(globalThis, "fetch", async (_: URL, init: RequestInit) => {
    calls++; assert.deepEqual(JSON.parse(init.body as string), c); return Response.json(expected);
  });
  await check(await POST(request(c)), 200, expected);
  assert.equal(calls, 1);
});

test("actual POST rejects media type, JSON syntax and invalid claim without upstream activity", async t => {
  let calls = 0; t.mock.method(globalThis, "fetch", async () => { calls++; throw new Error("unexpected"); });
  assert.equal(runtime, "nodejs");
  for (const ct of [null, "text/plain", "application/problem+json", "application/json-fake"]) await check(await POST(request(claim(), ct)), 400, { error: "INVALID_CLAIM" });
  await check(await POST(new Request("http://web.test", { method: "POST", headers: { "Content-Type": "application/json" }, body: "SYNTHETIC_PRIVATE_BAD_JSON" })), 400, { error: "INVALID_CLAIM" });
  for (const value of [null, [], {}, { ...claim(), kind: "generated_roleplay" }, { ...claim(), sources: [...claim().sources, { ...claim().sources[0], title: " " }] }]) await check(await POST(request(value)), 400, { error: "INVALID_CLAIM" });
  assert.equal(calls, 0);
});

test("projects full success with duplicates, mixed negatives, Unicode and registered-empty results", async t => {
  const previous = process.env.PENSIEVE_API_ORIGIN;
  t.after(() => { if (previous === undefined) delete process.env.PENSIEVE_API_ORIGIN; else process.env.PENSIEVE_API_ORIGIN = previous; });
  process.env.PENSIEVE_API_ORIGIN = "http://backend.test:8100";
  const c = claim(); c.sources = Array.from({ length: 6 }, () => structuredClone(c.sources[0]));
  const statuses = ["REGISTRY_MATCH", "SOURCE_NOT_REGISTERED", "REGISTRY_MATCH", "SOURCE_METADATA_MISMATCH", "LOCATOR_NOT_REGISTERED", "REGISTRY_MATCH"];
  const expected = { statement: c.statement, references: c.sources.map((reference, i) => ({ reference, status: statuses[i], passages: i === 0 || i === 5 ? ["arrival", "departure"].map(passage_id => ({ kind: "source_passage", passage_id, reference, text: "Inès au café.\nTwo  lanterns." })) : [] })), all_references_registered: false, all_references_have_passages: false };
  let calls = 0;
  t.mock.method(globalThis, "fetch", async (url: URL, init: RequestInit) => {
    calls++; assert.equal(String(url), "http://backend.test:8100/api/v1/claims/passages/lookup");
    assert.equal(init.method, "POST"); assert.deepEqual(init.headers, { Accept: "application/json", "Content-Type": "application/json" });
    assert.deepEqual(JSON.parse(init.body as string), c); assert.equal(init.cache, "no-store"); assert.equal(init.redirect, "error"); assert.ok(init.signal instanceof AbortSignal);
    return Response.json(expected, { headers: { "X-Private": "SYNTHETIC_PRIVATE" } });
  });
  for (const ct of ["application/json", "Application/JSON; Charset=UTF-8", "application/json ; charset=utf-8"]) await check(await POST(request(c, ct)), 200, expected);
  assert.equal(calls, 3);
});

test("maps default unconfigured API distinctly from service failure with bounded private errors", async t => {
  const previous = process.env.PENSIEVE_API_ORIGIN;
  t.after(() => { if (previous === undefined) delete process.env.PENSIEVE_API_ORIGIN; else process.env.PENSIEVE_API_ORIGIN = previous; });
  delete process.env.PENSIEVE_API_ORIGIN;
  let calls = 0;
  const mock = t.mock.method(globalThis, "fetch", async (url: URL) => { calls++; assert.equal(String(url), "http://127.0.0.1:8000/api/v1/claims/passages/lookup"); return Response.json({ detail: "Passage lookup is not configured" }, { status: 503 }); });
  await check(await POST(request()), 503, { error: "LOOKUP_NOT_CONFIGURED" }); assert.equal(calls, 1);
  for (const status of [422, 500, 503]) {
    mock.mock.mockImplementation(async () => Response.json({ detail: "SYNTHETIC_PRIVATE" }, { status }));
    await check(await POST(request()), 502, { error: "LOOKUP_UNAVAILABLE" });
  }
  mock.mock.mockImplementation(async () => { throw new Error("SYNTHETIC_PRIVATE_TRANSPORT"); });
  await check(await POST(request()), 502, { error: "LOOKUP_UNAVAILABLE" });
  process.env.PENSIEVE_API_ORIGIN = "SYNTHETIC_PRIVATE_ORIGIN";
  await check(await POST(request()), 502, { error: "LOOKUP_UNAVAILABLE" });
});

test("unexpected route boundary failures remain bounded", async () => {
  const r = request(); Object.defineProperty(r, "headers", { get() { throw new Error("SYNTHETIC_PRIVATE"); } });
  await check(await POST(r), 502, { error: "LOOKUP_UNAVAILABLE" });
});
