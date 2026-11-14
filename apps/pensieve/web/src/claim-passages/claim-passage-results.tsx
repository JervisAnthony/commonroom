import type { Ref } from "react";
import type { ClaimPassageResponse, ResolutionStatus, SourceReference } from "./claim-passage-contract.ts";

const categories: Record<SourceReference["canon_tier"], string> = { book: "Book", film: "Film", expanded_publication: "Expanded publication" };
const statuses: Record<ResolutionStatus, string> = {
  REGISTRY_MATCH: "Citation matched", SOURCE_NOT_REGISTERED: "Source not registered",
  SOURCE_METADATA_MISMATCH: "Source metadata mismatch", LOCATOR_NOT_REGISTERED: "Locator not registered",
};
export default function ClaimPassageResults({ data, headingRef }: { data: ClaimPassageResponse; headingRef?: Ref<HTMLHeadingElement> }) {
  return <section className="lookup-results" aria-labelledby="lookup-result-title">
    <h2 id="lookup-result-title" tabIndex={-1} ref={headingRef}>Available passages</h2>
    <h3>Submitted statement</h3>
    <p className="lookup-text">{data.statement}</p>
    <dl className="lookup-aggregates">
      <div><dt>All citations matched</dt><dd>{data.all_references_registered ? "Yes" : "No"}</dd></div>
      <div><dt>Passages available for every citation</dt><dd>{data.all_references_have_passages ? "Yes" : "No"}</dd></div>
    </dl>
    <ol className="lookup-outcomes">
      {data.references.map((outcome, index) => <li key={index}>
        <article>
          <h3>Citation {index + 1}: {statuses[outcome.status]}</h3>
          <dl className="lookup-metadata">
            <div><dt>Source ID</dt><dd className="lookup-text">{outcome.reference.source_id}</dd></div>
            <div><dt>Source title</dt><dd className="lookup-text">{outcome.reference.title}</dd></div>
            <div><dt>Source category</dt><dd>{categories[outcome.reference.canon_tier]}</dd></div>
            <div><dt>Locator kind</dt><dd>{outcome.reference.locator.kind}</dd></div>
            <div><dt>Locator reference</dt><dd className="lookup-text">{outcome.reference.locator.reference}</dd></div>
          </dl>
          {outcome.passages.length > 0 ? <ol className="lookup-passages">
            {outcome.passages.map(passage => <li key={passage.passage_id}>
              <h4>Passage ID: <span className="lookup-text">{passage.passage_id}</span></h4>
              <p className="lookup-text">{passage.text}</p>
            </li>)}
          </ol> : <p>{outcome.status === "REGISTRY_MATCH"
            ? "This citation matched registered metadata in this service, but no passage text is available here."
            : "No passages are available for this citation in this service."}</p>}
        </article>
      </li>)}
    </ol>
    <p className="lookup-note">Matching metadata and available text do not establish authenticity, licensing or rights, canonical truth, or support for your statement.</p>
  </section>;
}
