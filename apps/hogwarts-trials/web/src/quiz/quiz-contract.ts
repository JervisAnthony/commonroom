// Public wire contracts only. Parsers project allowlisted fields at both boundaries.
export type Summary = {
  quiz_id: string;
  title: string;
  description: string | null;
  question_count: number;
};
export type Question = {
  position: number;
  question_id: string;
  prompt: string;
  question_type: "single_choice" | "multiple_choice";
  difficulty: "easy" | "medium" | "hard";
  choices: {
    choice_id: string;
    text: string;
  }[];
};
export type Quiz = Omit<Summary, "question_count"> & {
  questions: Question[];
};
export type Submission = {
  question_id: string;
  selected_choice_ids: string[];
};
export type QuestionResult = Submission & {
  status: "correct" | "incorrect" | "unanswered";
  awarded_points: number;
  max_points: number;
};
export type Grade = {
  quiz_id: string;
  question_results: QuestionResult[];
  total_points: number;
  max_points: number;
  correct_count: number;
  incorrect_count: number;
  unanswered_count: number;
};
export const isUuid = (v: unknown): v is string => typeof v === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(v);
function fail(): never { throw new Error("Unexpected quiz service response. Please try again."); }
function obj(v: unknown): Record<string, unknown> { return v !== null && typeof v === "object" && !Array.isArray(v) ? v as Record<string, unknown> : fail(); }
function str(v: unknown): string { return typeof v === "string" && v.trim() ? v : fail(); }
function id(v: unknown): string { return isUuid(v) ? v.toLowerCase() : fail(); }
function num(v: unknown, min = 0): number { return typeof v === "number" && Number.isSafeInteger(v) && v >= min ? v : fail(); }
function arr(v: unknown): unknown[] { return Array.isArray(v) ? v : fail(); }
function unique<T>(items: T[], key: (item: T) => unknown): T[] { return new Set(items.map(key)).size === items.length ? items : fail(); }
function base(v: unknown) { const o = obj(v); return { quiz_id: id(o.quiz_id), title: str(o.title), description: o.description === null ? null : str(o.description) }; }
export function parseCatalog(v: unknown): Summary[] {
  return unique(arr(v).map(value => ({ ...base(value), question_count: num(obj(value).question_count, 1) })), q => q.quiz_id);
}
export function parseQuiz(v: unknown): Quiz {
  const questions = unique(arr(obj(v).questions).map((value): Question => {
    const q = obj(value);
    if (q.question_type !== "single_choice" && q.question_type !== "multiple_choice")
      fail();
    if (q.difficulty !== "easy" && q.difficulty !== "medium" && q.difficulty !== "hard")
      fail();
    const choices = unique(arr(q.choices).map(value => { const c = obj(value); return { choice_id: id(c.choice_id), text: str(c.text) }; }), c => c.choice_id);
    if (choices.length < 2 || choices.length > 8)
      fail();
    return { position: num(q.position, 1), question_id: id(q.question_id), prompt: str(q.prompt), question_type: q.question_type, difficulty: q.difficulty, choices };
  }), q => q.question_id).sort((a, b) => a.position - b.position);
  if (!questions.length || questions.some((q, i) => q.position !== i + 1))
    fail();
  return { ...base(v), questions };
}
export function parseSubmissions(v: unknown): {
  submissions: Submission[];
} {
  const o = obj(v);
  if (Object.keys(o).some(k => k !== "submissions"))
    fail();
  return {
    submissions: unique(arr(o.submissions).map(value => {
      const s = obj(value);
      if (Object.keys(s).some(k => k !== "question_id" && k !== "selected_choice_ids"))
        fail();
      const selected_choice_ids = unique(arr(s.selected_choice_ids).map(id), c => c);
      if (!selected_choice_ids.length)
        fail();
      return { question_id: id(s.question_id), selected_choice_ids };
    }), s => s.question_id)
  };
}
export function parseGrade(v: unknown): Grade {
  const o = obj(v);
  const question_results = unique(arr(o.question_results).map((value): QuestionResult => {
    const r = obj(value);
    if (r.status !== "correct" && r.status !== "incorrect" && r.status !== "unanswered")
      fail();
    const selected_choice_ids = unique(arr(r.selected_choice_ids).map(id), c => c);
    const awarded_points = num(r.awarded_points), max_points = num(r.max_points, 1);
    if (max_points !== 1 || awarded_points !== (r.status === "correct" ? 1 : 0) || (r.status === "unanswered") !== (selected_choice_ids.length === 0))
      fail();
    return { question_id: id(r.question_id), status: r.status, selected_choice_ids, awarded_points, max_points };
  }), r => r.question_id);
  const grade = { quiz_id: id(o.quiz_id), question_results, total_points: num(o.total_points), max_points: num(o.max_points, 1), correct_count: num(o.correct_count), incorrect_count: num(o.incorrect_count), unanswered_count: num(o.unanswered_count) };
  if (grade.max_points !== question_results.length || grade.total_points !== question_results.reduce((n, r) => n + r.awarded_points, 0))
    fail();
  for (const status of ["correct", "incorrect", "unanswered"] as const)
    if (grade[`${status}_count`] !== question_results.filter(r => r.status === status).length)
      fail();
  return grade;
}
export function matchGrade(grade: Grade, quiz: Quiz, submissions: Submission[]): Grade {
  if (grade.quiz_id !== quiz.quiz_id || grade.question_results.length !== quiz.questions.length)
    fail();
  for (const q of quiz.questions) {
    const r = grade.question_results.find(r => r.question_id === q.question_id);
    const selected = submissions.find(s => s.question_id === q.question_id)?.selected_choice_ids ?? [];
    if (!r || r.selected_choice_ids.length !== selected.length || r.selected_choice_ids.some(c => !selected.includes(c)))
      fail();
  }
  return grade;
}
