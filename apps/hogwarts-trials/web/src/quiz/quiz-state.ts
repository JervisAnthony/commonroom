import type { Quiz, Submission, Grade } from "./quiz-contract.ts";
export type Answers = Record<string, string[]>;
export function selectChoice(quiz: Quiz, answers: Answers, questionId: string, choiceId: string): Answers {
  const q = quiz.questions.find(q => q.question_id === questionId);
  if (!q || !q.choices.some(c => c.choice_id === choiceId))
    return answers;
  const selected = answers[questionId] ?? [];
  return { ...answers, [questionId]: q.question_type === "single_choice" ? [choiceId] : selected.includes(choiceId) ? selected.filter(c => c !== choiceId) : [...selected, choiceId] };
}
export function buildSubmissions(quiz: Quiz, answers: Answers): Submission[] {
  return [...quiz.questions].sort((a, b) => a.position - b.position).flatMap(q => {
    const choices = q.choices.filter(c => answers[q.question_id]?.includes(c.choice_id)).map(c => c.choice_id).sort();
    return choices.length ? [{ question_id: q.question_id, selected_choice_ids: q.question_type === "single_choice" ? choices.slice(0, 1) : choices }] : [];
  });
}
export type Run = {
  answers: Answers;
  phase: "playing" | "submitting" | "results";
  result: Grade | null;
  error: string | null;
};
export const freshRun = (): Run => ({ answers: {}, phase: "playing", result: null, error: null });
export function submissionFailed(run: Run, error: string): Run { return { ...run, phase: "playing", error }; }
