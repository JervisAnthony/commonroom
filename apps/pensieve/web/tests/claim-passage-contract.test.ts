import assert from "node:assert/strict";
import { test } from "node:test";
import { parseSourcedLoreClaim, parseClaimPassageResponse, type SourcedLoreClaim, type ClaimPassageResponse, type ResolutionStatus } from "../src/claim-passages/claim-passage-contract.ts";

function claim(): SourcedLoreClaim {
  return { kind: "sourced_lore", statement: "A fictional lantern arrives.", sources: [{ source_id: "synthetic-atlas", title: "The Folded Lantern Atlas", canon_tier: "book", locator: { kind: "chapter", reference: "A" } }] };
}
function response(c = claim()): ClaimPassageResponse {
  return { statement: c.statement, references: c.sources.map(reference => ({ reference: structuredClone(reference), status: "REGISTRY_MATCH", passages: ["arrival", "departure"].map(passage_id => ({ kind: "source_passage", passage_id, reference: structuredClone(reference), text: "Inès at the café.\nTwo  lanterns." })) })), all_references_registered: true, all_references_have_passages: true };
}

test("rejects lone or embedded surrogates in every request text field, including later citations", () => {
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
    for (const c of invalid) assert.equal(parseSourcedLoreClaim(c), null);
  }
});

test("rejects malformed response passage IDs and text without repairing them", () => {
  for (const value of ["\ud800", "\udfff", "before\ud800after", "before\udfffafter"]) {
    for (const key of ["passage_id", "text"] as const) {
      const r = response(); r.references[0].passages[0][key] = value;
      const before = structuredClone(r);
      assert.equal(parseClaimPassageResponse(r, claim()), null);
      assert.deepEqual(r, before);
    }
  }
});

test("preserves valid supplementary pairs in all text fields and response passages", () => {
  for (const value of ["\ud83d\ude80", "\ud800\udc00", "before\u{1f680}\u{10000}after"]) {
    const c = claim(); c.statement = value;
    Object.assign(c.sources[0], { source_id: value, title: value }); c.sources[0].locator.reference = value;
    assert.deepEqual(parseSourcedLoreClaim(c), c);
    const r = response(c);
    r.references[0].passages.forEach((p, i) => { p.passage_id = value + i; p.text = value; });
    assert.deepEqual(parseClaimPassageResponse(r, c), r);
  }
});

test("normalizes all request text with Pydantic Unicode whitespace, preserving BOM and interior content", () => {
  for (const whitespace of [" \t\r\n", "\u0085", "\u00a0", "\u1680", "\u2000\u200a\u2028\u2029\u202f\u205f\u3000"]) {
    const c = claim();
    c.statement = whitespace + "Inès  au café.\nLantern" + whitespace;
    c.sources[0].source_id = whitespace + "Case-Sensitive" + whitespace;
    c.sources[0].title = whitespace + c.sources[0].title + whitespace;
    c.sources[0].locator.reference = whitespace + "A" + whitespace;
    const parsed = parseSourcedLoreClaim(c)!;
    assert.equal(parsed.statement, "Inès  au café.\nLantern");
    assert.equal(parsed.sources[0].source_id, "Case-Sensitive");
    assert.equal(parsed.sources[0].title, claim().sources[0].title);
    assert.equal(parsed.sources[0].locator.reference, "A");
    assert.equal(parseSourcedLoreClaim({ ...c, statement: whitespace }), null);
  }
  for (const s of ["\ufeff", "x", "\u200b", "\u001c"]) assert.equal(parseSourcedLoreClaim({ ...claim(), statement: s })?.statement, s);
});

test("required own fields and exact keys at every request object", () => {
  for (const select of [(c: SourcedLoreClaim) => c, (c: SourcedLoreClaim) => c.sources[0], (c: SourcedLoreClaim) => c.sources[0].locator]) {
    const seed = select(claim());
    for (const key of Object.keys(seed)) {
      const c = claim();
      delete (select(c) as Record<string, unknown>)[key];
      assert.equal(parseSourcedLoreClaim(c), null, key);
      const inherited = claim();
      const o = select(inherited) as Record<string, unknown>;
      const value = o[key]; delete o[key]; Object.setPrototypeOf(o, { [key]: value });
      assert.equal(parseSourcedLoreClaim(inherited), null);
    }
    const c = claim(); Object.assign(select(c), { private: "SYNTHETIC_PRIVATE" });
    assert.equal(parseSourcedLoreClaim(c), null);
  }
});

test("rejects wrong request primitives, literals, containers, blank text and invalid final citations", () => {
  for (const value of [null, [], "claim", 1, true, {}, { ...claim(), kind: "generated_roleplay" }, { ...claim(), kind: " sourced_lore" }, { ...claim(), sources: [] }, { ...claim(), sources: {} }]) assert.equal(parseSourcedLoreClaim(value), null);
  const paths = [["statement"], ["sources", 0, "source_id"], ["sources", 0, "title"], ["sources", 0, "locator", "reference"], ["sources", 0, "canon_tier"], ["sources", 0, "locator", "kind"], ["sources", 0, "locator"], ["sources", 0]];
  for (const path of paths) for (const bad of [null, [], {}, 0, false, "", " \u0085\u00a0"]) {
    const c = structuredClone(claim());
    let o: unknown = c;
    for (const key of path.slice(0, -1)) o = (o as Record<string | number, unknown>)[key];
    (o as Record<string | number, unknown>)[path[path.length - 1]] = bad;
    assert.equal(parseSourcedLoreClaim(c), null);
  }
  for (const bad of ["BOOK", " book", "game"]) assert.equal(parseSourcedLoreClaim({ ...claim(), sources: [{ ...claim().sources[0], canon_tier: bad }] }), null);
  assert.equal(parseSourcedLoreClaim({ ...claim(), sources: [...claim().sources, { ...claim().sources[0], title: null }] }), null);
  assert.equal(parseSourcedLoreClaim({ ...claim(), sources: new Array(1) }), null);
});

test("all statuses and ordered repeated citations retain normal negative and registered-empty outcomes", () => {
  const c = claim(); const ref = c.sources[0];
  c.sources = [ref, ref, ref, ref, ref, ref];
  const r = response(c);
  const statuses: ResolutionStatus[] = ["REGISTRY_MATCH", "SOURCE_NOT_REGISTERED", "SOURCE_METADATA_MISMATCH", "LOCATOR_NOT_REGISTERED", "REGISTRY_MATCH", "REGISTRY_MATCH"];
  r.references.forEach((outcome, i) => { outcome.status = statuses[i]; if (i > 0 && i < 5) outcome.passages = []; });
  r.all_references_registered = false; r.all_references_have_passages = false;
  assert.deepEqual(parseClaimPassageResponse(r, c), r);
  const empty = response(); empty.references[0].passages = []; empty.all_references_have_passages = false;
  assert.deepEqual(parseClaimPassageResponse(empty, claim()), empty);
});

test("response exact required fields and types at every object level", () => {
  const selectors = [
    (r: ClaimPassageResponse) => r, (r: ClaimPassageResponse) => r.references[0],
    (r: ClaimPassageResponse) => r.references[0].reference, (r: ClaimPassageResponse) => r.references[0].reference.locator,
    (r: ClaimPassageResponse) => r.references[0].passages[0], (r: ClaimPassageResponse) => r.references[0].passages[0].reference,
    (r: ClaimPassageResponse) => r.references[0].passages[0].reference.locator,
  ];
  for (const select of selectors) {
    for (const key of Object.keys(select(response()))) {
      for (const value of [undefined, null, [], {}, 1, false]) {
        const r = response(); const o = select(r) as Record<string, unknown>;
        if (value === undefined) delete o[key]; else o[key] = value;
        assert.equal(parseClaimPassageResponse(r, claim()), null, key);
      }
      const r = response(); const o = select(r) as Record<string, unknown>;
      const value = o[key]; delete o[key]; Object.setPrototypeOf(o, { [key]: value });
      assert.equal(parseClaimPassageResponse(r, claim()), null);
    }
    const r = response(); Object.assign(select(r), { private: "SYNTHETIC_PRIVATE" });
    assert.equal(parseClaimPassageResponse(r, claim()), null);
  }
});

test("rejects every response binding and aggregate inconsistency", () => {
  const mutations: ((r: ClaimPassageResponse) => void)[] = [
    r => { r.statement += " changed"; }, r => { r.statement = " " + r.statement; },
    r => { r.references = []; }, r => { r.references.push(structuredClone(r.references[0])); },
    r => { r.references[0].reference.source_id = "SYNTHETIC-atlas"; },
    r => { r.references[0].reference.title += "!"; }, r => { r.references[0].reference.canon_tier = "film"; },
    r => { r.references[0].reference.locator.kind = "other"; }, r => { r.references[0].reference.locator.reference = "B"; },
    r => { r.references[0].passages[0].reference.title += "!"; },
    r => { r.references[0].passages[0].kind = "generated_roleplay" as "source_passage"; },
    r => { r.references[0].passages[0].text = "\u0085"; }, r => { r.references[0].passages[0].text += " "; },
    r => { r.references[0].passages[0].passage_id = " "; }, r => { r.references[0].passages[0].passage_id += " "; },
    r => { r.references[0].passages[1].passage_id = r.references[0].passages[0].passage_id; },
    r => { r.references[0].status = "SOURCE_NOT_REGISTERED"; r.all_references_registered = false; r.all_references_have_passages = false; },
    r => { r.all_references_registered = false; }, r => { r.all_references_have_passages = false; },
    r => { r.references[0].passages = []; },
  ];
  for (const mutate of mutations) { const r = response(); mutate(r); assert.equal(parseClaimPassageResponse(r, claim()), null); }
  for (const status of ["SOURCE_METADATA_MISMATCH", "LOCATOR_NOT_REGISTERED"]) {
    const r = response(); r.references[0].status = status as ResolutionStatus;
    r.all_references_registered = false; r.all_references_have_passages = false;
    assert.equal(parseClaimPassageResponse(r, claim()), null);
  }
  const c = claim(); c.sources.push({ ...c.sources[0], title: "Another title" });
  const r = response(c); r.references.reverse(); assert.equal(parseClaimPassageResponse(r, c), null);
  const empty = { ...response(), references: [] };
  for (const b of [true, false]) {
    assert.equal(parseClaimPassageResponse({ ...empty, all_references_registered: b, all_references_have_passages: b }, { ...claim(), sources: [] }), null);
    assert.equal(parseClaimPassageResponse({ ...empty, all_references_registered: b, all_references_have_passages: b }, claim()), null);
  }
  assert.equal(parseClaimPassageResponse({ ...response(), references: new Array(1) }, claim()), null);
  const negative = response(); negative.references[0].passages = []; negative.references[0].status = "SOURCE_NOT_REGISTERED";
  negative.all_references_registered = false; negative.all_references_have_passages = false;
  assert.deepEqual(parseClaimPassageResponse(negative, claim()), negative);
  for (const key of ["all_references_registered", "all_references_have_passages"] as const) {
    assert.equal(parseClaimPassageResponse({ ...negative, [key]: true }, claim()), null);
    for (const value of ["false", "true", 0, 1]) assert.equal(parseClaimPassageResponse({ ...negative, [key]: value }, claim()), null);
  }
  for (const v of [null, [], 1, true, "wire"]) assert.equal(parseClaimPassageResponse(v, claim()), null);
});

test("request and response snapshots own every repeated nested object, without input mutations", () => {
  const c = claim(); c.sources.push(c.sources[0]);
  const original = structuredClone(c); const parsed = parseSourcedLoreClaim(c)!;
  assert.deepEqual(c, original); assert.notEqual(parsed.sources[0], parsed.sources[1]);
  const r = response(c); r.references[1] = r.references[0];
  r.references[0].passages[1].reference = r.references[0].passages[0].reference;
  const before = structuredClone(r); const result = parseClaimPassageResponse(r, c)!;
  assert.deepEqual(r, before); assert.deepEqual(result, before);
  assert.notEqual(result.references[0], result.references[1]);
  assert.notEqual(result.references[0].passages, result.references[1].passages);
  assert.notEqual(result.references[0].passages[0].reference.locator, result.references[0].passages[1].reference.locator);
  c.sources[0].title = "changed"; r.references[0].passages[0].text = "changed";
  parsed.sources[0].locator.reference = "changed";
  assert.equal(parsed.sources[1].locator.reference, "A");
  assert.deepEqual(result, before);
  result.references[0].passages[0].reference.title = "changed";
  assert.equal(result.references[1].passages[0].reference.title, original.sources[0].title);
  assert.deepEqual(parseClaimPassageResponse(before, original), before);
});
