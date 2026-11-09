// Product-local public wire adapter. No I/O or claim-support verification.
export type SourceReference = {
  source_id: string;
  title: string;
  canon_tier: "book" | "film" | "expanded_publication";
  locator: { kind: "chapter" | "scene" | "section" | "other"; reference: string };
};
export type SourcedLoreClaim = { kind: "sourced_lore"; statement: string; sources: SourceReference[] };
export type ResolutionStatus = "SOURCE_NOT_REGISTERED" | "SOURCE_METADATA_MISMATCH" | "LOCATOR_NOT_REGISTERED" | "REGISTRY_MATCH";
export type SourcePassage = { kind: "source_passage"; passage_id: string; reference: SourceReference; text: string };
export type ReferencePassagesResponse = { reference: SourceReference; status: ResolutionStatus; passages: SourcePassage[] };
export type ClaimPassageResponse = {
  statement: string;
  references: ReferencePassagesResponse[];
  all_references_registered: boolean;
  all_references_have_passages: boolean;
};

function fail(): never { throw new Error("Invalid claim passage wire data"); }
function object(value: unknown, keys: string[]): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) fail();
  const own = Reflect.ownKeys(value);
  if (own.length !== keys.length || keys.some(key => !Object.prototype.hasOwnProperty.call(value, key))) fail();
  return value as Record<string, unknown>;
}
// Pydantic-core's Unicode White_Space set: includes NEL, excludes BOM.
// Explicit characters keep this compatible with the repository's ES2017 target.
function text(value: unknown, normalized: boolean): string {
  if (typeof value !== "string" || !value.isWellFormed()) fail();
  const stripped = value.replace(/^[\u0009-\u000d\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+|[\u0009-\u000d\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+$/g, "");
  if (!stripped || (normalized && stripped !== value)) fail();
  return stripped;
}
function literal<T extends string>(value: unknown, allowed: readonly T[]): T {
  for (const item of allowed) if (value === item) return item;
  return fail();
}
function array(value: unknown): unknown[] { return Array.isArray(value) ? Array.from(value) : fail(); }
function reference(value: unknown, normalized: boolean): SourceReference {
  const r = object(value, ["source_id", "title", "canon_tier", "locator"]);
  const l = object(r.locator, ["kind", "reference"]);
  return {
    source_id: text(r.source_id, normalized), title: text(r.title, normalized),
    canon_tier: literal(r.canon_tier, ["book", "film", "expanded_publication"]),
    locator: { kind: literal(l.kind, ["chapter", "scene", "section", "other"]), reference: text(l.reference, normalized) },
  };
}
function same(a: SourceReference, b: SourceReference): boolean {
  return a.source_id === b.source_id && a.title === b.title && a.canon_tier === b.canon_tier &&
    a.locator.kind === b.locator.kind && a.locator.reference === b.locator.reference;
}
export function parseSourcedLoreClaim(value: unknown): SourcedLoreClaim | null {
  try {
    const c = object(value, ["kind", "statement", "sources"]);
    const sources = array(c.sources).map(value => reference(value, false));
    if (!sources.length) fail();
    return { kind: literal(c.kind, ["sourced_lore"]), statement: text(c.statement, false), sources };
  } catch { return null; }
}
export function parseClaimPassageResponse(value: unknown, claim: unknown): ClaimPassageResponse | null {
  try {
    const snapshot = parseSourcedLoreClaim(claim);
    if (!snapshot) fail();
    const body = object(value, ["statement", "references", "all_references_registered", "all_references_have_passages"]);
    const statement = text(body.statement, true);
    const outcomes = array(body.references);
    if (statement !== snapshot.statement || outcomes.length !== snapshot.sources.length) fail();
    const references = outcomes.map((value, index): ReferencePassagesResponse => {
      const r = object(value, ["reference", "status", "passages"]);
      const ref = reference(r.reference, true);
      if (!same(ref, snapshot.sources[index])) fail();
      const status = literal(r.status, ["SOURCE_NOT_REGISTERED", "SOURCE_METADATA_MISMATCH", "LOCATOR_NOT_REGISTERED", "REGISTRY_MATCH"]);
      const passages = array(r.passages).map((value): SourcePassage => {
        const p = object(value, ["kind", "passage_id", "reference", "text"]);
        const citation = reference(p.reference, true);
        if (!same(citation, ref)) fail();
        return { kind: literal(p.kind, ["source_passage"]), passage_id: text(p.passage_id, true), reference: citation, text: text(p.text, true) };
      });
      if ((status !== "REGISTRY_MATCH" && passages.length) || new Set(passages.map(p => p.passage_id)).size !== passages.length) fail();
      return { reference: ref, status, passages };
    });
    const registered = references.length > 0 && references.every(r => r.status === "REGISTRY_MATCH");
    const available = registered && references.every(r => r.passages.length > 0);
    if (body.all_references_registered !== registered || body.all_references_have_passages !== available) fail();
    return { statement, references, all_references_registered: registered, all_references_have_passages: available };
  } catch { return null; }
}
