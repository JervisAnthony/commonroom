"use client";

import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { requestClaimPassages } from "./claim-passage-client.ts";
import { freshLookupState, editStatement, editCitation, addCitation, removeCitation, beginSubmission, completeSubmission, type LookupState, type CitationField } from "./claim-passage-state.ts";
import ClaimPassageResults from "./claim-passage-results";

const messages = {
  invalid_request: "Check your statement and every citation. All text fields must contain valid, nonblank text.",
  not_configured: "Passage lookup is not configured for this service yet. Your entries are still here; you can try again later.",
  unavailable: "Passage lookup is temporarily unavailable. Your entries are still here. Please try again.",
};

export default function ClaimPassageForm() {
  const [state, setState] = useState(freshLookupState);
  const current = useRef(state);
  const active = useRef<{ id: number; controller: AbortController } | null>(null);
  const errorRef = useRef<HTMLDivElement>(null);
  const resultRef = useRef<HTMLHeadingElement>(null);
  const rowFocus = useRef<string | null>(null);
  const prefix = useId();
  const busy = state.phase === "submitting";
  const rowId = (key: number, field: CitationField) => `${prefix}-${key}-${field}`;

  function publish(next: LookupState) { current.current = next; setState(next); }
  useEffect(() => () => {
    const request = active.current;
    active.current = null;
    request?.controller.abort();
  }, []);
  useEffect(() => {
    if (rowFocus.current) {
      document.getElementById(rowFocus.current)?.focus(); rowFocus.current = null;
    } else if (state.phase === "error") errorRef.current?.focus();
    else if (state.phase === "success") resultRef.current?.focus();
  }, [state]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const start = beginSubmission(current.current);
    publish(start.state);
    if (!start.submission) return;
    const request = { id: start.submission.id, controller: new AbortController() };
    active.current = request;
    const outcome = await requestClaimPassages(start.submission.claim, { signal: request.controller.signal });
    // An obsolete completion may neither publish nor clear a newer busy guard.
    if (active.current !== request) return;
    active.current = null;
    publish(completeSubmission(current.current, request.id, outcome));
  }
  function addRow() {
    const previous = current.current; const next = addCitation(previous);
    if (next === previous) return;
    rowFocus.current = rowId(next.citations[next.citations.length - 1].rowKey, "sourceId");
    publish(next);
  }
  function removeRow(key: number) {
    const previous = current.current; const index = previous.citations.findIndex(row => row.rowKey === key);
    const next = removeCitation(previous, key);
    if (next === previous) return;
    rowFocus.current = rowId(next.citations[Math.min(index, next.citations.length - 1)].rowKey, "sourceId");
    publish(next);
  }

  return <>
    <form method="post" action="/api/claims/passages/lookup" onSubmit={submit} aria-busy={busy}>
      <noscript><p>JavaScript is required for JSON passage lookup. Submitting without it cannot perform a lookup. This form uses POST, so entries will not appear in a GET query string.</p></noscript>
      <fieldset className="lookup-editor" disabled={busy}>
        <legend>Your statement and citations</legend>
        <label htmlFor={`${prefix}-statement`}>Statement</label>
        <p id={`${prefix}-statement-help`} className="lookup-help">Use an originally phrased statement. This lookup does not evaluate its support.</p>
        <textarea id={`${prefix}-statement`} required rows={4} value={state.statement} aria-describedby={`${prefix}-statement-help`} onChange={event => publish(editStatement(current.current, event.target.value))} />
        <h2>Ordered citations</h2>
        <p className="lookup-help" id={`${prefix}-citation-help`}>Enter the source metadata exactly. Source IDs are case-sensitive text. Repeated citations stay separate. Line breaks and interior spaces are preserved.</p>
        <ol className="lookup-citations">
          {state.citations.map((row, index) => <li key={row.rowKey}>
            <fieldset className="lookup-citation" aria-describedby={`${prefix}-citation-help`}>
              <legend>Citation {index + 1}</legend>
              <div className="lookup-fields">
                {([{ field: "sourceId", label: "Source ID" }, { field: "title", label: "Source title" }] as const).map(({ field, label }) => <div key={field}>
                  <label htmlFor={rowId(row.rowKey, field)}>{label}</label>
                  <textarea id={rowId(row.rowKey, field)} required rows={2} value={row[field]} onChange={event => publish(editCitation(current.current, row.rowKey, field, event.target.value))} />
                </div>)}
                <div><label htmlFor={rowId(row.rowKey, "category")}>Source category</label>
                  <select id={rowId(row.rowKey, "category")} value={row.category} onChange={event => publish(editCitation(current.current, row.rowKey, "category", event.target.value))}>
                    <option value="book">Book</option><option value="film">Film</option><option value="expanded_publication">Expanded publication</option>
                  </select>
                </div>
                <div><label htmlFor={rowId(row.rowKey, "locatorKind")}>Locator kind</label>
                  <select id={rowId(row.rowKey, "locatorKind")} value={row.locatorKind} onChange={event => publish(editCitation(current.current, row.rowKey, "locatorKind", event.target.value))}>
                    <option value="chapter">Chapter</option><option value="scene">Scene</option><option value="section">Section</option><option value="other">Other</option>
                  </select>
                </div>
                <div className="lookup-locator"><label htmlFor={rowId(row.rowKey, "locatorReference")}>Locator reference</label>
                  <textarea id={rowId(row.rowKey, "locatorReference")} required rows={2} value={row.locatorReference} onChange={event => publish(editCitation(current.current, row.rowKey, "locatorReference", event.target.value))} />
                </div>
              </div>
              <button type="button" disabled={state.citations.length === 1} onClick={() => removeRow(row.rowKey)} aria-label={`Remove citation ${index + 1}`}>Remove citation</button>
            </fieldset>
          </li>)}
        </ol>
        <button type="button" onClick={addRow}>Add citation</button>
      </fieldset>
      <button className="lookup-submit" type="submit" disabled={busy}>Look up passages</button>
      <p role="status" aria-live="polite">{busy ? "Looking up passages…" : state.phase === "idle" ? "Ready when you are. Nothing is submitted until you look up passages." : "Lookup finished."}</p>
    </form>
    {state.error && <div className="lookup-error" ref={errorRef} tabIndex={-1} role="alert"><h2>Lookup could not complete</h2><p>{messages[state.error]}</p></div>}
    {state.result && <ClaimPassageResults data={state.result} headingRef={resultRef} />}
  </>;
}
