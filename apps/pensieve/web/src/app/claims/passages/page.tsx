import type { Metadata } from "next";
import Link from "next/link";
import ClaimPassageForm from "../../../claim-passages/claim-passage-form";

export const metadata: Metadata = {
  title: "Claim passage lookup | Pensieve",
  description: "Look up available passages for an originally phrased statement and ordered source citations.",
};
export default function ClaimPassagesPage() {
  return <main id="main" className="lookup-page" tabIndex={-1}>
    <header className="lookup-introduction">
      <Link href="/">Back to Pensieve</Link>
      <p className="eyebrow">Exact citation lookup</p>
      <h1>Claim passage lookup</h1>
      <p className="lead">An original statement. Your citations. Available passages.</p>
      <p>Enter one or more citations to look for text held by this service. This is exact metadata lookup, not search, question answering, or an evaluation of your statement.</p>
      <p className="lookup-note">Configured passage text is publicly readable without application authorization. Matching and availability establish no authenticity, licensing or rights, canonical truth, or claim support. Your draft and results stay only in this page’s memory; refreshing or leaving clears them.</p>
    </header>
    <ClaimPassageForm />
  </main>;
}
