"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { parseCatalog, type Summary } from "../quiz/quiz-contract.ts";
import { errorMessage, readQuizResponse } from "../quiz/quiz-client.ts";
export function Catalog() {
  const [quizzes, setQuizzes] = useState<Summary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  function load(signal?: AbortSignal) {
    return fetch("/api/quizzes", { signal, cache: "no-store" })
      .then(readQuizResponse).then(parseCatalog)
      .then(data => {
        if (!signal?.aborted)
          setQuizzes(data);
      })
      .catch(e => {
        if (!signal?.aborted)
          setError(errorMessage(e));
      })
      .finally(() => {
        if (!signal?.aborted)
          setLoading(false);
      });
  }
  function retry() { setLoading(true); setError(null); void load(); }
  useEffect(() => { const controller = new AbortController(); void load(controller.signal); return () => controller.abort(); }, []);
  return <section id="trials" aria-labelledby="catalog-title" className="catalog">
    <div className="section-heading">
      <div>
        <p className="eyebrow">The reading room</p>
        <h2 id="catalog-title">Explore the Trials</h2>
      </div>
      <span className="tag">Synthetic demo catalog</span>
    </div>
    <p className="muted">Original demonstration questions to try the experience. Curated Harry Potter canon is still to come.</p>
    <div aria-live="polite" aria-busy={loading}>{loading ? <div className="notice">Opening the catalog…</div> : error ? <div className="notice">
      <h3>The catalog is unavailable</h3>
      <p role="alert">{error}</p>
      <button onClick={retry}>Try again</button>
    </div> : quizzes?.length === 0 ? <div className="notice">
      <h3>The shelves are quiet</h3>
      <p>No quizzes are available yet. Check again soon.</p>
      <button onClick={retry}>Refresh catalog</button>
    </div> : <div className="quiz-grid">{quizzes?.map((quiz, i) => <article className="quiz-card" key={quiz.quiz_id}>
      <div className="card-top">
        <span className="folio" aria-hidden="true">{String(i + 1).padStart(2, "0")}</span>
        <span className="tag">Demo trial</span>
      </div>
      <p className="eyebrow">{quiz.question_count} {quiz.question_count === 1 ? "question" : "questions"} · At your own pace</p>
      <h3>{quiz.title}</h3>
      <p>{quiz.description ?? "Take a seat and explore this trial."}</p>
      <Link className="button" href={`/quizzes/${quiz.quiz_id}`}>Begin this trial <span aria-hidden="true">→</span>
      </Link>
    </article>)}</div>}</div>
  </section>;
}
