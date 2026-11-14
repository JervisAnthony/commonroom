import assert from "node:assert/strict";
import { test } from "node:test";
import { spawnSync } from "node:child_process";
import { setImmediate } from "node:timers/promises";
import { requestClaimPassages } from "../src/claim-passages/claim-passage-client.ts";
import type { ClaimPassageResponse, SourcedLoreClaim } from "../src/claim-passages/claim-passage-contract.ts";

function claim(): SourcedLoreClaim { return { kind: "sourced_lore", statement: "A lantern arrives.", sources: [{ source_id: "synthetic-atlas", title: "The Folded Lantern Atlas", canon_tier: "book", locator: { kind: "chapter", reference: "A" } }] }; }
function data(c = claim()): ClaimPassageResponse { return { statement: c.statement, references: c.sources.map(reference => ({ reference: structuredClone(reference), status: "REGISTRY_MATCH", passages: ["arrival", "departure"].map(passage_id => ({ kind: "source_passage", passage_id, reference: structuredClone(reference), text: "Inès at the café.\nTwo  lanterns. 🚀" })) })), all_references_registered: true, all_references_have_passages: true }; }

test("browser client import performs zero requests", () => {
  const url = new URL("../src/claim-passages/claim-passage-client.ts", import.meta.url).href;
  const child = spawnSync(process.execPath, ["--input-type=module", "-e", `globalThis.fetch = () => process.exit(9); await import(${JSON.stringify(url)});`], { encoding: "utf8" });
  assert.equal(child.status, 0, child.stderr);
});

test("invalid claims, malformed UTF-16 and invalid final citations perform zero requests", async () => {
  let calls = 0;
  for (const value of [null, {}, { ...claim(), statement: "\u0085" }, { ...claim(), statement: "\ud800" }, { ...claim(), kind: "generated_roleplay" }, { ...claim(), sources: [...claim().sources, { ...claim().sources[0], title: "\udfff" }] }]) {
    assert.deepEqual(await requestClaimPassages(value, { fetcher: async () => { calls++; return Response.json(data()); } }), { status: "invalid_request" });
  }
  assert.equal(calls, 0);
});

test("fixed relative request, exact options and owned normalized snapshot before yielding", async () => {
  const c = claim(); c.statement = "\u0085 " + c.statement + "\u00a0"; c.sources[0].title = " " + c.sources[0].title;
  let calls = 0;
  const pending = requestClaimPassages(c, { fetcher: async (url, init) => {
    calls++; assert.equal(url, "/api/claims/passages/lookup"); assert.equal(init?.method, "POST");
    assert.deepEqual(init?.headers, { Accept: "application/json", "Content-Type": "application/json" });
    assert.deepEqual(JSON.parse(init?.body as string), claim());
    assert.equal(init?.cache, "no-store"); assert.equal(init?.redirect, "error"); assert.equal(init?.credentials, "omit");
    assert.ok(init?.signal instanceof AbortSignal); assert.equal(init.signal.aborted, false);
    await setImmediate(); return Response.json(data());
  } });
  c.statement = "changed"; c.sources[0].locator.reference = "changed";
  assert.deepEqual(await pending, { status: "ok", data: data() }); assert.equal(calls, 1);
});

test("strict validated ordered mixed/repeated/registered-empty data passes with Unicode intact", async () => {
  const c = claim(); c.sources = Array.from({ length: 6 }, () => structuredClone(c.sources[0]));
  const result = data(c);
  result.references.forEach((r, i) => {
    if (i > 0 && i < 5) r.passages = [];
    r.status = (["REGISTRY_MATCH", "SOURCE_NOT_REGISTERED", "SOURCE_METADATA_MISMATCH", "LOCATOR_NOT_REGISTERED", "REGISTRY_MATCH", "REGISTRY_MATCH"] as const)[i];
  });
  result.all_references_registered = false; result.all_references_have_passages = false;
  const parsed = await requestClaimPassages(c, { fetcher: async () => Response.json(result) });
  assert.deepEqual(parsed, { status: "ok", data: result });
  if (parsed.status === "ok") { result.references[0].passages[0].text = "mutated"; assert.notEqual(parsed.data.references[0].passages[0].text, "mutated"); }
});

test("malformed, extra, mismatched, reordered and inconsistent success data fail closed", async () => {
  const c = claim(); c.sources.push({ ...c.sources[0], title: "Another title" });
  const mutations: ((r: ClaimPassageResponse) => void)[] = [
    r => { r.statement += "!"; }, r => { r.references.reverse(); }, r => { r.references.pop(); },
    r => { r.references[0].reference.source_id = "wrong"; }, r => { r.all_references_registered = false; },
    r => { r.all_references_have_passages = false; }, r => { Object.assign(r, { private: "SYNTHETIC_PRIVATE" }); },
    r => { Object.assign(r.references[0].passages[0], { private: "SYNTHETIC_PRIVATE" }); },
    r => { r.references[0].passages[0].text = "\udfff"; }, r => { r.references[0].passages[0].passage_id = "\ud800"; },
    r => { r.references[0].passages[0].reference.title = "wrong"; },
    r => { r.references[0].passages[1].passage_id = r.references[0].passages[0].passage_id; },
  ];
  for (const mutate of mutations) { const r = data(c); mutate(r); assert.deepEqual(await requestClaimPassages(c, { fetcher: async () => Response.json(r) }), { status: "unavailable" }); }
  for (const raw of [null, [], true, 1, "SYNTHETIC_PRIVATE", {}]) assert.deepEqual(await requestClaimPassages(c, { fetcher: async () => Response.json(raw) }), { status: "unavailable" });
});

test("only exact bounded HTTP/error combinations are recognized without leaking private bodies", async t => {
  const log = t.mock.method(console, "log"), error = t.mock.method(console, "error");
  for (const [status, code, result] of [[400, "INVALID_CLAIM", "invalid_request"], [503, "LOOKUP_NOT_CONFIGURED", "not_configured"], [502, "LOOKUP_UNAVAILABLE", "unavailable"]] as const) {
    assert.deepEqual(await requestClaimPassages(claim(), { fetcher: async () => Response.json({ error: code }, { status }) }), { status: result });
    for (const raw of [null, [], {}, { detail: code }, { error: "SYNTHETIC_PRIVATE" }, { error: code, private: "SYNTHETIC_PRIVATE" }]) assert.deepEqual(await requestClaimPassages(claim(), { fetcher: async () => Response.json(raw, { status }) }), { status: "unavailable" });
  }
  for (const status of [201, 204, 302, 401, 404, 422, 500]) assert.deepEqual(await requestClaimPassages(claim(), { fetcher: async () => new Response(null, { status }) }), { status: "unavailable" });
  assert.deepEqual(await requestClaimPassages(claim(), { fetcher: async () => Response.json({ error: "LOOKUP_NOT_CONFIGURED" }, { status: 400 }) }), { status: "unavailable" });
  assert.equal(log.mock.callCount(), 0); assert.equal(error.mock.callCount(), 0);
});

test("JSON media type casing/charset, malformed JSON and redirects are handled strictly", async () => {
  for (const status of [200, 503]) {
    const raw = status === 200 ? data() : { error: "LOOKUP_NOT_CONFIGURED" };
    for (const type of ["application/json", "Application/JSON; Charset=UTF-8", "application/json ; charset=utf-8"]) assert.equal((await requestClaimPassages(claim(), { fetcher: async () => new Response(JSON.stringify(raw), { status, headers: { "Content-Type": type } }) })).status, status === 200 ? "ok" : "not_configured");
    for (const type of [null, "text/plain", "application/problem+json", "application/json-fake"]) assert.deepEqual(await requestClaimPassages(claim(), { fetcher: async () => new Response(JSON.stringify(raw), { status, headers: type ? { "Content-Type": type } : {} }) }), { status: "unavailable" });
    assert.deepEqual(await requestClaimPassages(claim(), { fetcher: async () => new Response("SYNTHETIC_PRIVATE_BAD_JSON", { status, headers: { "Content-Type": "application/json" } }) }), { status: "unavailable" });
    const redirected = Response.json(raw, { status }); Object.defineProperty(redirected, "redirected", { value: true });
    assert.deepEqual(await requestClaimPassages(claim(), { fetcher: async () => redirected }), { status: "unavailable" });
  }
});

for (const phase of ["fetch", "success-body", "error-body"] as const) for (const aware of [false, true]) {
  test(`deadline bounds ${phase}, abort aware=${aware}, and removes timers/listeners`, async t => {
    t.mock.timers.enable({ apis: ["setTimeout"] }); const cleared = t.mock.method(globalThis, "clearTimeout");
    const external = new AbortController(); const removed = t.mock.method(external.signal, "removeEventListener");
    let signal: AbortSignal | undefined; let reading = false;
    const pending = requestClaimPassages(claim(), { signal: external.signal, fetcher: async (_, init) => {
      signal = init?.signal as AbortSignal; assert.notEqual(signal, external.signal);
      const hang = <T>() => new Promise<T>((_, reject) => { if (aware) signal!.addEventListener("abort", () => reject(new Error("SYNTHETIC_PRIVATE_ABORT")), { once: true }); });
      if (phase === "fetch") return hang<Response>();
      const r = Response.json({}, { status: phase === "success-body" ? 200 : 503 }); r.json = () => { reading = true; return hang(); }; return r;
    } });
    await setImmediate(); assert.equal(reading, phase !== "fetch");
    t.mock.timers.tick(4999); assert.equal(signal?.aborted, false);
    t.mock.timers.tick(1); assert.deepEqual(await pending, { status: "unavailable" });
    assert.equal(signal?.aborted, true); assert.equal(cleared.mock.callCount(), 1); assert.equal(removed.mock.callCount(), 1);
  });
}

test("pre-aborted signals never fetch", async () => {
  const controller = new AbortController(); controller.abort(); let calls = 0;
  assert.deepEqual(await requestClaimPassages(claim(), { signal: controller.signal, fetcher: async () => { calls++; return Response.json(data()); } }), { status: "unavailable" });
  assert.equal(calls, 0);
});

for (const phase of ["fetch", "body"]) test(`external cancellation bounds abort-ignoring ${phase} and contains late rejection`, async t => {
  const controller = new AbortController(); let rejectLate: (reason: Error) => void = () => {};
  let signal: AbortSignal | undefined;
  const removed = t.mock.method(controller.signal, "removeEventListener");
  const pending = requestClaimPassages(claim(), { signal: controller.signal, fetcher: async (_, init) => {
    signal = init?.signal as AbortSignal;
    if (phase === "fetch") return new Promise<Response>((_, reject) => { rejectLate = reject; });
    const r = Response.json(data()); r.json = () => new Promise((_, reject) => { rejectLate = reject; }); return r;
  } });
  await setImmediate(); controller.abort(); assert.deepEqual(await pending, { status: "unavailable" });
  assert.equal(signal?.aborted, true); assert.equal(removed.mock.callCount(), 1);
  rejectLate(new Error("SYNTHETIC_PRIVATE_LATE")); await setImmediate();
});

test("fresh calls clean up success/failure timers and listeners; transport/body errors are bounded", async t => {
  t.mock.timers.enable({ apis: ["setTimeout"] }); const cleared = t.mock.method(globalThis, "clearTimeout");
  const controller = new AbortController(); const removed = t.mock.method(controller.signal, "removeEventListener");
  const signals: AbortSignal[] = []; let calls = 0;
  const log = t.mock.method(console, "log"), error = t.mock.method(console, "error");
  const fetcher: typeof fetch = async (_, init) => {
    calls++; signals.push(init?.signal as AbortSignal);
    if (calls === 2) throw new Error("SYNTHETIC_PRIVATE_TRANSPORT");
    const r = Response.json(data()); if (calls === 3) r.json = async () => { throw new Error("SYNTHETIC_PRIVATE_BODY"); }; return r;
  };
  for (const status of ["ok", "unavailable", "unavailable", "ok"]) assert.equal((await requestClaimPassages(claim(), { fetcher, signal: controller.signal })).status, status);
  assert.equal(calls, 4); assert.equal(cleared.mock.callCount(), 4); assert.equal(removed.mock.callCount(), 4);
  t.mock.timers.tick(6000); controller.abort(); assert.ok(signals.every(s => !s.aborted));
  assert.equal(log.mock.callCount(), 0); assert.equal(error.mock.callCount(), 0);
});

test("custom timeout and late success cannot change a completed cancellation result", async t => {
  t.mock.timers.enable({ apis: ["setTimeout"] }); let resolveLate: (response: Response) => void = () => {};
  const pending = requestClaimPassages(claim(), { timeoutMs: 7, fetcher: async () => new Promise<Response>(resolve => { resolveLate = resolve; }) });
  t.mock.timers.tick(7); const outcome = await pending; assert.deepEqual(outcome, { status: "unavailable" });
  resolveLate(Response.json(data())); await setImmediate(); assert.deepEqual(outcome, { status: "unavailable" });
});
