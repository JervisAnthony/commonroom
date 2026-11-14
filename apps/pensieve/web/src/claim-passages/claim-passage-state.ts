import { parseSourcedLoreClaim, parseClaimPassageResponse, type ClaimPassageResponse, type SourcedLoreClaim } from "./claim-passage-contract.ts";
import type { ClaimPassageClientResult } from "./claim-passage-client.ts";

export type CitationDraft = {
  rowKey: number; sourceId: string; title: string; category: string; locatorKind: string; locatorReference: string;
};
export type CitationField = Exclude<keyof CitationDraft, "rowKey">;
export type LookupState = {
  statement: string; citations: CitationDraft[]; nextRowKey: number; nextRequestId: number;
  activeRequestId: number | null; phase: "idle" | "submitting" | "success" | "error";
  result: ClaimPassageResponse | null; error: Exclude<ClaimPassageClientResult["status"], "ok"> | null;
};
const blankCitation = (rowKey: number): CitationDraft => ({ rowKey, sourceId: "", title: "", category: "book", locatorKind: "chapter", locatorReference: "" });
export const freshLookupState = (): LookupState => ({
  statement: "", citations: [blankCitation(0)], nextRowKey: 1, nextRequestId: 1,
  activeRequestId: null, phase: "idle", result: null, error: null,
});
function edited(state: LookupState): LookupState { return { ...state, phase: "idle", result: null, error: null }; }
export function editStatement(state: LookupState, statement: string): LookupState {
  return state.phase === "submitting" ? state : { ...edited(state), statement };
}
export function editCitation(state: LookupState, rowKey: number, field: CitationField, value: string): LookupState {
  if (state.phase === "submitting" || !state.citations.some(row => row.rowKey === rowKey)) return state;
  return { ...edited(state), citations: state.citations.map(row => row.rowKey === rowKey ? { ...row, [field]: value } : row) };
}
export function addCitation(state: LookupState): LookupState {
  return state.phase === "submitting" ? state : { ...edited(state), citations: [...state.citations, blankCitation(state.nextRowKey)], nextRowKey: state.nextRowKey + 1 };
}
export function removeCitation(state: LookupState, rowKey: number): LookupState {
  if (state.phase === "submitting" || state.citations.length === 1 || !state.citations.some(row => row.rowKey === rowKey)) return state;
  return { ...edited(state), citations: state.citations.filter(row => row.rowKey !== rowKey) };
}
export function claimFromDraft(state: LookupState): SourcedLoreClaim | null {
  return parseSourcedLoreClaim({ kind: "sourced_lore", statement: state.statement, sources: state.citations.map(row => ({
    source_id: row.sourceId, title: row.title, canon_tier: row.category,
    locator: { kind: row.locatorKind, reference: row.locatorReference },
  })) });
}
// The form writes this transition to its ref synchronously, before invoking fetch.
export function beginSubmission(state: LookupState): {
  state: LookupState; submission: { id: number; claim: SourcedLoreClaim } | null;
} {
  if (state.phase === "submitting") return { state, submission: null };
  const claim = claimFromDraft(state);
  if (!claim) return { state: { ...state, phase: "error", result: null, error: "invalid_request" }, submission: null };
  const id = state.nextRequestId;
  return { state: { ...state, phase: "submitting", activeRequestId: id, nextRequestId: id + 1, result: null, error: null }, submission: { id, claim } };
}
export function completeSubmission(state: LookupState, id: number, outcome: ClaimPassageClientResult): LookupState {
  if (state.phase !== "submitting" || state.activeRequestId !== id) return state;
  const data = outcome.status === "ok" ? parseClaimPassageResponse(outcome.data, claimFromDraft(state)) : null;
  return data
    ? { ...state, activeRequestId: null, phase: "success", result: data, error: null }
    : { ...state, activeRequestId: null, phase: "error", result: null, error: outcome.status === "ok" ? "unavailable" : outcome.status };
}
