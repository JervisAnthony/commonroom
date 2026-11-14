import assert from "node:assert/strict";
import { test } from "node:test";
import { freshLookupState, editStatement, editCitation, addCitation, removeCitation, claimFromDraft, beginSubmission, completeSubmission, type LookupState } from "../src/claim-passages/claim-passage-state.ts";
import type { ClaimPassageResponse } from "../src/claim-passages/claim-passage-contract.ts";

function ready(): LookupState {
  let state = editStatement(freshLookupState(), " \u0085A lantern  arrives.\nAt dawn.\u00a0");
  for (const [field, value] of Object.entries({ sourceId: " synthetic-atlas ", title: "The Folded Lantern Atlas", locatorReference: "A" })) {
    state = editCitation(state, 0, field as "sourceId" | "title" | "locatorReference", value);
  }
  return state;
}
function response(state: LookupState): ClaimPassageResponse {
  const claim = claimFromDraft(state)!;
  return { statement: claim.statement, references: claim.sources.map(reference => ({ reference, status: "REGISTRY_MATCH", passages: [] })), all_references_registered: true, all_references_have_passages: false };
}

test("fresh drafts are blank, independently owned and idle with exactly one citation", () => {
  const a = freshLookupState(), b = freshLookupState();
  assert.equal(a.statement, ""); assert.equal(a.citations.length, 1); assert.equal(a.phase, "idle");
  assert.equal(a.result, null); assert.equal(a.error, null); assert.equal(a.activeRequestId, null);
  assert.deepEqual(a.citations[0], { rowKey: 0, sourceId: "", title: "", category: "book", locatorKind: "chapter", locatorReference: "" });
  a.citations[0].title = "changed"; assert.equal(b.citations[0].title, "");
});

test("add/remove preserve surviving identities, values and order; final row cannot be removed", () => {
  const original = ready(); const state = addCitation(addCitation(original));
  assert.deepEqual(state.citations.map(r => r.rowKey), [0, 1, 2]);
  const removed = removeCitation(state, 1); const added = addCitation(removed);
  assert.deepEqual(added.citations.map(r => r.rowKey), [0, 2, 3]);
  assert.deepEqual(added.citations[0], original.citations[0]);
  assert.equal(removeCitation(original, 0), original); assert.equal(removeCitation(state, 99), state);
  assert.deepEqual(state.citations.map(r => r.rowKey), [0, 1, 2]);
});

test("repeated citations edit independently and wire projection excludes all UI fields", () => {
  let state = addCitation(ready());
  const first = state.citations[0];
  for (const field of ["sourceId", "title", "category", "locatorKind", "locatorReference"] as const) state = editCitation(state, 1, field, first[field]);
  const claim = claimFromDraft(state)!;
  assert.equal(claim.statement, "A lantern  arrives.\nAt dawn.");
  assert.deepEqual(claim.sources[0], claim.sources[1]); assert.notEqual(claim.sources[0], claim.sources[1]);
  assert.deepEqual(Object.keys(claim), ["kind", "statement", "sources"]);
  assert.deepEqual(Object.keys(claim.sources[0]), ["source_id", "title", "canon_tier", "locator"]);
  const edited = editCitation(state, 1, "title", "Another title");
  assert.equal(edited.citations[0].title, first.title); assert.equal(state.citations[1].title, first.title);
  claim.sources[0].locator.reference = "mutated"; assert.equal(state.citations[0].locatorReference, "A");
});

test("complete draft validation blocks blank, malformed and invalid later citations before submission", () => {
  for (const state of [freshLookupState(), addCitation(ready()), editStatement(ready(), "\ud800"), editCitation(ready(), 0, "title", "\udfff"), editCitation(ready(), 0, "category", "BOOK"), editCitation(ready(), 0, "locatorReference", "\u0085")]) {
    const start = beginSubmission(state); assert.equal(start.submission, null);
    assert.equal(start.state.phase, "error"); assert.equal(start.state.error, "invalid_request");
    assert.deepEqual(start.state.citations, state.citations); assert.equal(start.state.statement, state.statement);
  }
});

test("submission owns its normalized snapshot and blocks synchronous duplicate submissions and edits", () => {
  const initial = ready(); const start = beginSubmission(initial);
  assert.ok(start.submission); assert.equal(start.state.phase, "submitting");
  assert.equal(beginSubmission(start.state).submission, null);
  assert.equal(beginSubmission(start.state).state, start.state);
  assert.equal(editStatement(start.state, "changed"), start.state);
  assert.equal(editCitation(start.state, 0, "title", "changed"), start.state);
  assert.equal(addCitation(start.state), start.state); assert.equal(removeCitation(start.state, 0), start.state);
  initial.citations[0].locatorReference = "changed"; assert.equal(start.submission.claim.sources[0].locator.reference, "A");
});

test("failure keeps inputs, allows manual retry and rejects stale completion IDs", () => {
  const start = beginSubmission(ready());
  const failed = completeSubmission(start.state, start.submission!.id, { status: "unavailable" });
  assert.equal(failed.phase, "error"); assert.deepEqual(failed.citations, start.state.citations);
  const retry = beginSubmission(failed); assert.ok(retry.submission); assert.equal(retry.state.error, null);
  assert.notEqual(retry.submission.id, start.submission!.id);
  assert.equal(completeSubmission(retry.state, start.submission!.id, { status: "not_configured" }), retry.state);
  assert.equal(retry.state.activeRequestId, retry.submission.id);
  for (const status of ["invalid_request", "not_configured", "unavailable"] as const) {
    const result = completeSubmission(retry.state, retry.submission.id, { status }); assert.equal(result.error, status);
  }
});

test("success owns its snapshot; new submission and draft edits clear stale results/errors", () => {
  const start = beginSubmission(ready()); const data = response(start.state);
  const success = completeSubmission(start.state, start.submission!.id, { status: "ok", data });
  assert.equal(success.phase, "success"); assert.deepEqual(success.result, data);
  data.references[0].reference.title = "mutated"; assert.notEqual(success.result!.references[0].reference.title, "mutated");
  const saved = structuredClone(success.result);
  const edited = editCitation(success, 0, "title", "New title"); assert.equal(edited.result, null); assert.equal(edited.error, null);
  assert.deepEqual(success.result, saved);
  for (const next of [editStatement(success, "New statement"), addCitation(success), beginSubmission(success).state]) assert.equal(next.result, null);
  const failed = completeSubmission(start.state, start.submission!.id, { status: "unavailable" });
  assert.equal(editStatement(failed, "changed").error, null); assert.equal(addCitation(failed).error, null);
  const two = addCitation(success); assert.equal(removeCitation(two, 1).result, null);
});

test("completion cannot publish without an active matching request or accept unbound data", () => {
  const initial = ready(); assert.equal(completeSubmission(initial, 1, { status: "unavailable" }), initial);
  const start = beginSubmission(initial); const data = response(initial); data.statement = "wrong statement";
  const result = completeSubmission(start.state, start.submission!.id, { status: "ok", data });
  assert.equal(result.result, null); assert.equal(result.error, "unavailable");
  assert.equal(completeSubmission(result, start.submission!.id, { status: "ok", data: response(initial) }), result);
});
