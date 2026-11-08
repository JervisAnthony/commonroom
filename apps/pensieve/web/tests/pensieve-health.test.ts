import assert from "node:assert/strict";
import { test } from "node:test";
import { spawnSync } from "node:child_process";
import { setImmediate } from "node:timers/promises";
import { checkPensieveHealth } from "../src/server/pensieve-health.ts";

const healthy = { status: "ok", service: "pensieve-api" };
const json = (body: unknown = healthy) => Response.json(body);
const local = { origin: "http://127.0.0.1:8000" };

test("import has no network side effect in a fresh process", () => {
  const moduleUrl = new URL("../src/server/pensieve-health.ts", import.meta.url).href;
  const result = spawnSync(process.execPath, ["--experimental-strip-types", "--input-type=module", "-e",
    `let calls = 0; globalThis.fetch = () => { calls++; throw new Error('Unexpected fetch'); }; await import(${JSON.stringify(moduleUrl)}); if (calls !== 0) process.exit(1);`], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr);
});

test("accepts normal HTTP(S) origins, slash and custom port; uses exact request contract", async () => {
  for (const origin of ["http://127.0.0.1:8000", "http://localhost/", "https://example.test:8443/", "HTTPS://example.test", "http://[::1]:8100"]) {
    let calls = 0;
    const fetcher: typeof fetch = async (url, init) => {
      calls++;
      assert.equal(String(url), new URL("/api/v1/health", origin).href);
      assert.equal(init?.method, "GET");
      assert.deepEqual(init?.headers, { Accept: "application/json" });
      assert.equal(init?.cache, "no-store");
      assert.equal(init?.redirect, "error");
      assert.ok(init?.signal instanceof AbortSignal);
      assert.equal(init.signal.aborted, false);
      return json();
    };
    assert.equal(await checkPensieveHealth({ origin, fetcher }), "available");
    assert.equal(calls, 1);
  }
});

test("reads server environment at call time, defaults only when absent", async (t) => {
  const seen: string[] = [];
  const fetcher: typeof fetch = async url => { seen.push(String(url)); return json(); };
  t.after(() => { if (previous === undefined) delete process.env.PENSIEVE_API_ORIGIN; else process.env.PENSIEVE_API_ORIGIN = previous; });
  const previous = process.env.PENSIEVE_API_ORIGIN;
  delete process.env.PENSIEVE_API_ORIGIN;
  assert.equal(await checkPensieveHealth({ fetcher }), "available");
  process.env.PENSIEVE_API_ORIGIN = "https://example.test:8443/";
  assert.equal(await checkPensieveHealth({ fetcher }), "available");
  process.env.PENSIEVE_API_ORIGIN = "";
  assert.equal(await checkPensieveHealth({ fetcher }), "unavailable");
  assert.deepEqual(seen, ["http://127.0.0.1:8000/api/v1/health", "https://example.test:8443/api/v1/health"]);
});

test("rejects invalid configuration before fetch", async () => {
  for (const origin of ["", " ", "nonsense", "//example.test", "ftp://example.test", "http:example.test", "https:///example.test", "https://user:secret@example.test", "https://@example.test", "https://example.test?", "https://example.test?q=private", "https://example.test#", "https://example.test#private", "https://example.test/prefix", "https://example.test/prefix/..", "https://example.test/./", "https://example.test//", " https://example.test", "https://exam\tple.test", "https://example.test\n", "https://example.test\\prefix", "https://example.test:99999"]) {
    let calls = 0;
    assert.equal(await checkPensieveHealth({ origin, fetcher: async () => { calls++; return json(); } }), "unavailable", origin);
    assert.equal(calls, 0, origin);
  }
});

test("accepts only exact health fields and discards additional private data", async () => {
  assert.equal(await checkPensieveHealth({ ...local, fetcher: async () => json({ ...healthy, private: "SYNTHETIC_PRIVATE_PAYLOAD" }) }), "available");
  for (const body of [null, [], [healthy], "ok", 1, true, {}, { status: "ok" }, { service: "pensieve-api" }, { ...healthy, status: "OK" }, { ...healthy, status: true }, { ...healthy, status: ["ok"] }, { ...healthy, service: "other" }, { ...healthy, service: "pensieve-api " }, { ...healthy, service: null }, { ...healthy, service: ["pensieve-api"] }]) {
    assert.equal(await checkPensieveHealth({ ...local, fetcher: async () => json(body) }), "unavailable");
  }
});

test("requires HTTP 200, JSON media type and valid JSON", async () => {
  for (const status of [201, 204, 301, 302, 400, 503]) {
    assert.equal(await checkPensieveHealth({ ...local, fetcher: async () => new Response(null, { status }) }), "unavailable");
  }
  for (const contentType of [null, "text/plain", "application/problem+json", "application/json-fake", "text/application/json"]) {
    assert.equal(await checkPensieveHealth({ ...local, fetcher: async () => new Response(JSON.stringify(healthy), { headers: contentType ? { "Content-Type": contentType } : {} }) }), "unavailable");
  }
  for (const contentType of ["application/json", "Application/JSON; Charset=UTF-8", "application/json ; charset=utf-8"]) {
    assert.equal(await checkPensieveHealth({ ...local, fetcher: async () => new Response(JSON.stringify(healthy), { headers: { "Content-Type": contentType } }) }), "available");
  }
  assert.equal(await checkPensieveHealth({ ...local, fetcher: async () => new Response("SYNTHETIC_PRIVATE_BAD_JSON", { headers: { "Content-Type": "application/json" } }) }), "unavailable");
  const redirected = json();
  Object.defineProperty(redirected, "redirected", { value: true });
  assert.equal(await checkPensieveHealth({ ...local, fetcher: async () => redirected }), "unavailable");
});

test("transport and response-reading failures return only unavailable", async () => {
  assert.equal(await checkPensieveHealth({ ...local, fetcher: async () => { throw new Error("SYNTHETIC_PRIVATE_TRANSPORT"); } }), "unavailable");
  const response = json();
  response.json = async () => { throw new Error("SYNTHETIC_PRIVATE_BODY"); };
  assert.equal(await checkPensieveHealth({ ...local, fetcher: async () => response }), "unavailable");
});

for (const phase of ["fetch", "body"] as const) {
  test(`deadline bounds ${phase} reading, aborts request and cleans timer`, async (t) => {
    t.mock.timers.enable({ apis: ["setTimeout"] });
    const cleared = t.mock.method(globalThis, "clearTimeout");
    let signal: AbortSignal | undefined;
    let bodyStarted = false;
    const fetcher: typeof fetch = async (_, init) => {
      signal = init?.signal as AbortSignal;
      if (phase === "fetch") return new Promise<Response>(() => {});
      const response = json();
      response.json = () => { bodyStarted = true; return new Promise(() => {}); };
      return response;
    };
    const pending = checkPensieveHealth({ ...local, fetcher });
    await setImmediate();
    assert.equal(bodyStarted, phase === "body");
    t.mock.timers.tick(2999);
    assert.equal(signal?.aborted, false);
    t.mock.timers.tick(1);
    assert.equal(await pending, "unavailable");
    assert.equal(signal?.aborted, true);
    assert.equal(cleared.mock.callCount(), 1);
  });
}

test("abort-aware transport rejection is contained", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const pending = checkPensieveHealth({ ...local, timeoutMs: 10, fetcher: async (_, init) => new Promise((_, reject) => {
    init?.signal?.addEventListener("abort", () => reject(new Error("SYNTHETIC_PRIVATE_ABORT")), { once: true });
  }) });
  t.mock.timers.tick(10);
  assert.equal(await pending, "unavailable");
});

test("abort during body reading is contained", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  let reading = false;
  const pending = checkPensieveHealth({ ...local, timeoutMs: 10, fetcher: async (_, init) => {
    const response = json();
    response.json = () => new Promise((_, reject) => {
      reading = true;
      init?.signal?.addEventListener("abort", () => reject(new Error("SYNTHETIC_PRIVATE_BODY_ABORT")), { once: true });
    });
    return response;
  } });
  await setImmediate();
  assert.equal(reading, true);
  t.mock.timers.tick(10);
  assert.equal(await pending, "unavailable");
});

test("clears deadline after success and failure; every invocation fetches afresh", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const cleared = t.mock.method(globalThis, "clearTimeout");
  const signals: AbortSignal[] = [];
  let calls = 0;
  const fetcher: typeof fetch = async (_, init) => {
    signals.push(init?.signal as AbortSignal);
    if (++calls === 2) throw new Error("SYNTHETIC_PRIVATE_FAILURE");
    return json();
  };
  assert.equal(await checkPensieveHealth({ ...local, fetcher }), "available");
  assert.equal(await checkPensieveHealth({ ...local, fetcher }), "unavailable");
  assert.equal(await checkPensieveHealth({ ...local, fetcher }), "available");
  assert.equal(calls, 3);
  assert.equal(cleared.mock.callCount(), 3);
  t.mock.timers.tick(5000);
  assert.ok(signals.every(signal => !signal.aborted));
});
