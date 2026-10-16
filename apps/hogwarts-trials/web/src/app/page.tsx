import { Catalog } from "../components/catalog.tsx";
export default function Home() {
  return <main id="main-content">
    <section className="hero">
      <div>
        <p className="eyebrow">An invitation to the curious</p>
        <h1>A little wonder.<br />
          <em>A test of knowledge.</em>
        </h1>
        <p className="hero-copy">Pull up a chair in the Commonroom. Follow your curiosity, consider each question, and discover how much you know.</p>
        <a className="button gold" href="#trials">Explore the Trials <span aria-hidden="true">↓</span>
        </a>
        <p className="small">No clock to race. No account required.</p>
      </div>
      <div className="astrolabe" aria-hidden="true">
        <span>✧</span>
        <b>KNOWLEDGE<br />&amp; WONDER</b>
      </div>
    </section>
    <Catalog />
    <aside className="study-note">
      <span aria-hidden="true">✧</span>
      <div>
        <h2>A practice in curiosity</h2>
        <p>Choose one answer or several, revisit a question, or leave it open. Submit when you are ready for your score and a review of your selections.</p>
      </div>
    </aside>
  </main>;
}
