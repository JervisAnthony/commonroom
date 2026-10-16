"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { isUuid, matchGrade, parseGrade, parseQuiz, type Quiz } from "../quiz/quiz-contract.ts";
import { buildSubmissions, freshRun, selectChoice, submissionFailed } from "../quiz/quiz-state.ts";
import { errorMessage, readQuizResponse } from "../quiz/quiz-client.ts";
export function QuizPlayer({ quizId }: {
  quizId: string;
}) {
  const [quiz, setQuiz] = useState<Quiz | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [index, setIndex] = useState(0);
  const [run, setRun] = useState(freshRun);
  const submitting = useRef(false);
  const questionHeading = useRef<HTMLLegendElement>(null);
  const resultHeading = useRef<HTMLHeadingElement>(null);
  async function load(signal?: AbortSignal) {
    setLoading(true);
    setLoadError(null);
    try {
      if (!isUuid(quizId))
        throw new Error("This trial link is invalid. Return to the catalog to choose a trial.");
      const data = parseQuiz(await readQuizResponse(await fetch(`/api/quizzes/${quizId}`, { signal, cache: "no-store" })));
      if (!signal?.aborted)
        setQuiz(data);
    }
    catch (e) {
      if (!signal?.aborted)
        setLoadError(errorMessage(e));
    }
    finally {
      if (!signal?.aborted)
        setLoading(false);
    }
  }
  useEffect(() => { const controller = new AbortController(); void load(controller.signal); return () => controller.abort(); }, [quizId]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (run.phase === "results")
      resultHeading.current?.focus();
  }, [run.phase]);
  function navigate(next: number) { setIndex(next); requestAnimationFrame(() => questionHeading.current?.focus()); }
  async function submit() {
    if (!quiz || submitting.current || run.phase !== "playing")
      return;
    submitting.current = true;
    setRun(current => ({ ...current, phase: "submitting", error: null }));
    const submissions = buildSubmissions(quiz, run.answers);
    try {
      const response = await fetch(`/api/quizzes/${quiz.quiz_id}/grade`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ submissions }) });
      const result = matchGrade(parseGrade(await readQuizResponse(response)), quiz, submissions);
      setRun(current => ({ ...current, phase: "results", result, error: null }));
    }
    catch (e) {
      setRun(current => submissionFailed(current, errorMessage(e)));
    }
    finally {
      submitting.current = false;
    }
  }
  const back = <Link className="back-link" href="/">← All trials</Link>;
  if (loading)
    return <>{back}<p className="notice" role="status">Preparing your trial…</p>
    </>;
  if (loadError || !quiz)
    return <>{back}<section className="notice">
      <h1>Unable to open this trial</h1>
      <p role="alert">{loadError}</p>
      <button onClick={() => void load()}>Try again</button>
    </section>
    </>;
  const answered = buildSubmissions(quiz, run.answers).length;
  const unanswered = quiz.questions.length - answered;
  if (run.phase === "results" && run.result) {
    const result = run.result;
    return <>{back}<section className="result-banner">
      <p className="eyebrow">Trial complete · Synthetic demo</p>
      <h1 tabIndex={-1} ref={resultHeading}>Your moment of reflection</h1>
      <p>{quiz.title}</p>
      <p className="score">{result.total_points}<span> / {result.max_points} points</span>
      </p>
      <dl className="totals">
        <div>
          <dt>Correct</dt>
          <dd>{result.correct_count}</dd>
        </div>
        <div>
          <dt>Incorrect</dt>
          <dd>{result.incorrect_count}</dd>
        </div>
        <div>
          <dt>Unanswered</dt>
          <dd>{result.unanswered_count}</dd>
        </div>
      </dl>
      <p className="small">Graded by the quiz service. This practice result is not saved to an account.</p>
      <div className="actions">
        <button className="gold" onClick={() => { setRun(freshRun()); setIndex(0); requestAnimationFrame(() => questionHeading.current?.focus()); }}>Start a fresh run</button>
        <Link className="button secondary" href="/">Explore more trials</Link>
      </div>
    </section>
      <section className="review" aria-labelledby="review-title">
        <p className="eyebrow">The annotated notebook</p>
        <h2 id="review-title">Review your selections</h2>
        <p className="muted">Outcomes are supplied by the service. Answer keys and explanations are not provided.</p>{quiz.questions.map(q => {
          const r = result.question_results.find(r => r.question_id === q.question_id)!;
          return <article className="review-card" key={q.question_id}>
            <div className="section-heading">
              <span className="eyebrow">Question {q.position}</span>
              <span className={`outcome ${r.status}`}>{r.status} · {r.awarded_points}/{r.max_points}</span>
            </div>
            <h3>{q.prompt}</h3>
            <p className="small">Your submitted selections</p>{r.selected_choice_ids.length ? <ul>{q.choices.filter(c => r.selected_choice_ids.includes(c.choice_id)).map(c => <li key={c.choice_id}>{c.text}</li>)}</ul> : <p>No answer submitted.</p>}</article>;
        })}</section>
    </>;
  }
  const q = quiz.questions[index];
  const busy = run.phase === "submitting";
  return <>{back}<header className="trial-heading">
    <p className="eyebrow">Practice trial · Synthetic demo</p>
    <h1>{quiz.title}</h1>
    <p>{quiz.description}</p>
  </header>
    <div className="player-layout">
      <aside className="notebook">
        <p className="eyebrow">Your progress</p>
        <p aria-live="polite">{answered} of {quiz.questions.length} answered</p>
        <progress value={answered} max={quiz.questions.length} aria-label="Questions answered" />
        <nav aria-label="Questions" className="question-nav">{quiz.questions.map((question, i) => <button key={question.question_id} disabled={busy} aria-current={i === index ? "step" : undefined} aria-label={`Question ${question.position}, ${run.answers[question.question_id]?.length ? "answered" : "unanswered"}`} onClick={() => navigate(i)}>{question.position}<span aria-hidden="true">{run.answers[question.question_id]?.length ? " ✓" : " ·"}</span>
        </button>)}</nav>
        <p className="small">Take your time. You can revisit any question before submitting.</p>
      </aside>
      <section className="question-panel" aria-label="Quiz player">
        <p className="eyebrow" aria-live="polite">Question {q.position} of {quiz.questions.length} <span className="difficulty">{q.difficulty}</span>
        </p>
        <form onSubmit={e => { e.preventDefault(); void submit(); }}>
          <fieldset disabled={busy}>
            <legend tabIndex={-1} ref={questionHeading}>{q.prompt}</legend>
            <p id="selection-hint">{q.question_type === "single_choice" ? "Choose one answer." : "Select all that apply. Select again to deselect."}</p>
            <div className="choices">{q.choices.map(c => <label className={`choice ${run.answers[q.question_id]?.includes(c.choice_id) ? "selected" : ""}`} key={c.choice_id}>
              <input type={q.question_type === "single_choice" ? "radio" : "checkbox"} name={q.question_id} value={c.choice_id} checked={run.answers[q.question_id]?.includes(c.choice_id) ?? false} aria-describedby="selection-hint" onChange={() => setRun(current => ({ ...current, answers: selectChoice(quiz, current.answers, q.question_id, c.choice_id), error: null }))} />
              <span>{c.text}</span>
            </label>)}</div>
            <button type="button" className="text-button" disabled={!run.answers[q.question_id]?.length} onClick={() => setRun(current => ({ ...current, answers: { ...current.answers, [q.question_id]: [] } }))}>Clear this answer</button>
          </fieldset>
          <div className="question-controls">
            <button type="button" className="secondary" disabled={index === 0 || busy} onClick={() => navigate(index - 1)}>← Previous</button>{index < quiz.questions.length - 1 ? <button type="button" disabled={busy} onClick={() => navigate(index + 1)}>{run.answers[q.question_id]?.length ? "Next question" : "Skip for now"} →</button> : <a href="#submit-trial" className="button secondary">Review submission ↓</a>}</div>
          <div id="submit-trial" className="submit-panel">
            <h2>Ready to close your notebook?</h2>
            <p aria-live="polite">{unanswered ? `${unanswered} of ${quiz.questions.length} questions remain unanswered. Submitting now will mark them unanswered.` : "Every question has a selection. You can still revisit your answers."}</p>{run.error && <p role="alert" className="error">{run.error} Your selections are preserved.</p>}<button className="gold" disabled={busy} type="submit">{busy ? "Grading your trial…" : unanswered ? `Submit with ${unanswered} unanswered` : "Submit for grading"}</button>
            <p className="small" role="status">{busy ? "Please wait while the service grades your answers." : "Your result is for this run only. Leaving or refreshing clears your work."}</p>
          </div>
        </form>
      </section>
    </div>
  </>;
}
