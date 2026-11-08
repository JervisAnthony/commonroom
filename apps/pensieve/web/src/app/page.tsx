import { checkPensieveHealth } from "../server/pensieve-health";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export default async function Home() {
  const available = await checkPensieveHealth() === "available";
  return (
    <main id="main" tabIndex={-1}>
      <section className="introduction" aria-labelledby="page-title">
        <p className="eyebrow">A Commonroom project</p>
        <h1 id="page-title">Pensieve</h1>
        <p className="lead">A place for thoughtful lore discovery, built around source provenance.</p>
        <p>This first web foundation lets you check whether the Pensieve service is reachable. Question answering and passage browsing are future work.</p>
        <div className="principle"><span aria-hidden="true">01</span><div><h2>Sources before stories</h2><p>Connectivity is one small step. Source attribution, passage availability, and verification are separate concerns.</p></div></div>
      </section>
      <section className="availability" aria-labelledby="availability-title">
        <p className="eyebrow">Service availability</p>
        <div className="status-mark" aria-hidden="true">{available ? "✓" : "—"}</div>
        <h2 id="availability-title">{available ? "Service reachable" : "Service unavailable"}</h2>
        <p>{available ? "The Pensieve service responded to this page's connectivity check." : "We could not confirm a connection to the Pensieve service. You can check again when you are ready."}</p>
        {/* A full document request intentionally refreshes the server health check. */}
        {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
        <a className="refresh" href="/">Refresh service status <span aria-hidden="true">↗</span></a>
        <p className="status-note">Checked when this page opened. Refresh to check again.</p>
      </section>
    </main>
  );
}
