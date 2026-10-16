import { test } from "node:test";
import assert from "node:assert/strict";
import { parseCatalog, parseQuiz, parseGrade, parseSubmissions, matchGrade, type Quiz } from "../src/quiz/quiz-contract.ts";
import { buildSubmissions, selectChoice, freshRun, submissionFailed } from "../src/quiz/quiz-state.ts";
import { quizApi } from "../src/quiz/server/quiz-api.ts";
import { GET as detailRoute } from "../src/app/api/quizzes/[quizId]/route.ts";
import { POST as gradeRoute } from "../src/app/api/quizzes/[quizId]/grade/route.ts";
const id = (n: number) => `10000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const quiz: Quiz = {
  quiz_id: id(1), title: "The practice notebook", description: null, questions: [
    { position: 1, question_id: id(10), prompt: "Choose a color", question_type: "single_choice", difficulty: "easy", choices: [{ choice_id: id(12), text: "Blue" }, { choice_id: id(11), text: "Green" }] },
    { position: 2, question_id: id(20), prompt: "Choose some shapes", question_type: "multiple_choice", difficulty: "medium", choices: [{ choice_id: id(22), text: "Circle" }, { choice_id: id(21), text: "Square" }, { choice_id: id(23), text: "Triangle" }] },
    { position: 3, question_id: id(30), prompt: "Choose a material", question_type: "single_choice", difficulty: "hard", choices: [{ choice_id: id(31), text: "Paper" }, { choice_id: id(32), text: "Stone" }] },
  ]
};
const grade = {
  quiz_id: id(1), question_results: [
    { question_id: id(10), status: "correct", selected_choice_ids: [id(12)], awarded_points: 1, max_points: 1 },
    { question_id: id(20), status: "incorrect", selected_choice_ids: [id(22)], awarded_points: 0, max_points: 1 },
    { question_id: id(30), status: "unanswered", selected_choice_ids: [], awarded_points: 0, max_points: 1 },
  ], total_points: 1, max_points: 3, correct_count: 1, incorrect_count: 1, unanswered_count: 1
};
const summary = { quiz_id: quiz.quiz_id, title: quiz.title, description: null, question_count: 3 };
const response = (data: unknown, status = 200) => Response.json(data, { status });
const configured = { baseUrl: "http://127.0.0.1:8000" };
const request = (data: unknown) => new Request("http://localhost/api/quizzes/grade", { method: "POST", body: JSON.stringify(data) });
test("single choice replaces selection using IDs, without duplicates", () => {
  let answers = selectChoice(quiz, {}, id(10), id(12));
  answers = selectChoice(quiz, answers, id(10), id(11));
  answers = selectChoice(quiz, answers, id(10), id(11));
  assert.deepEqual(answers, { [id(10)]: [id(11)] });
});
test("multiple choices toggle independently and deselect", () => {
  let answers = selectChoice(quiz, {}, id(20), id(22));
  answers = selectChoice(quiz, answers, id(20), id(21));
  assert.deepEqual(answers[id(20)], [id(22), id(21)]);
  answers = selectChoice(quiz, answers, id(20), id(22));
  assert.deepEqual(answers[id(20)], [id(21)]);
});
test("returning to questions retains independent selections", () => {
  let answers = selectChoice(quiz, {}, id(10), id(12));
  answers = selectChoice(quiz, answers, id(20), id(22));
  answers = selectChoice(quiz, answers, id(20), id(21));
  assert.deepEqual(answers[id(10)], [id(12)]);
  assert.equal(buildSubmissions(quiz, answers).length, 2);
});
test("unknown question and cross-question choice are rejected", () => {
  const answers = { [id(10)]: [id(12)] };
  assert.equal(selectChoice(quiz, answers, id(90), id(12)), answers);
  assert.equal(selectChoice(quiz, answers, id(10), id(22)), answers);
});
test("payload omits unanswered and orders questions by position and choices by ID", () => {
  const answers = { [id(20)]: [id(22), id(21), id(22), id(99)], [id(10)]: [id(12)], [id(30)]: [], [id(99)]: [id(11)] };
  assert.deepEqual(buildSubmissions({ ...quiz, questions: [...quiz.questions].reverse() }, answers), [
    { question_id: id(10), selected_choice_ids: [id(12)] },
    { question_id: id(20), selected_choice_ids: [id(21), id(22)] },
  ]);
  assert.deepEqual(buildSubmissions(quiz, {}), []);
});
test("failed submission preserves the same answers and permits retry; restart clears them", () => {
  const answers = { [id(10)]: [id(12)] };
  const run = submissionFailed({ ...freshRun(), answers, phase: "submitting" }, "Unavailable");
  assert.equal(run.answers, answers);
  assert.equal(run.phase, "playing");
  assert.equal(run.error, "Unavailable");
  assert.deepEqual(freshRun().answers, {});
});
test("catalog supports empty response and rejects malformed summaries", () => {
  assert.deepEqual(parseCatalog([]), []);
  assert.deepEqual(parseCatalog([summary]), [summary]);
  for (const v of [{ quizzes: [] }, [null], [{ ...summary, question_count: -1 }], [summary, summary]])
    assert.throws(() => parseCatalog(v));
});
test("detail sorts positions, validates types/IDs and strips private fields", () => {
  const raw = { ...quiz, correct_choice_ids: [id(11)], questions: [...quiz.questions].reverse().map(q => ({ ...q, explanation: "private", correct_choice_ids: [id(11)] })) };
  assert.deepEqual(parseQuiz(raw), quiz);
  assert.throws(() => parseQuiz({ ...quiz, questions: [{ ...quiz.questions[0], question_type: "essay" }] }));
  assert.throws(() => parseQuiz({ ...quiz, questions: [quiz.questions[0], quiz.questions[0]] }));
  assert.throws(() => parseQuiz({ ...quiz, quiz_id: "../attempts" }));
});
test("all grading outcomes and authoritative totals parse without any answer keys", () => {
  assert.deepEqual(parseGrade(grade), grade);
  assert.deepEqual(parseGrade({ ...grade, correct_choice_ids: [id(99)], question_results: grade.question_results.map(r => ({ ...r, correct_choice_ids: [id(99)], explanation: "private" })) }), grade);
  assert.deepEqual(matchGrade(parseGrade(grade), quiz, buildSubmissions(quiz, { [id(10)]: [id(12)], [id(20)]: [id(22)] })), grade);
});
test("inconsistent grade totals, counts, statuses and selections are rejected", () => {
  for (const raw of [{ ...grade, total_points: 3 }, { ...grade, max_points: 4 }, { ...grade, incorrect_count: 2 }, { ...grade, question_results: [{ ...grade.question_results[0], status: "unknown" }] }])
    assert.throws(() => parseGrade(raw));
  assert.throws(() => matchGrade(parseGrade(grade), quiz, []));
  assert.throws(() => matchGrade(parseGrade({ ...grade, quiz_id: id(9) }), quiz, []));
});
test("submission boundary rejects empty choices, duplicates and unexpected fields", () => {
  assert.deepEqual(parseSubmissions({ submissions: [] }), { submissions: [] });
  for (const raw of [{ submissions: [{ question_id: id(10), selected_choice_ids: [] }] }, { submissions: [{ question_id: id(10), selected_choice_ids: [id(11), id(11)] }] }, { submissions: [], url: "http://example.invalid" }])
    assert.throws(() => parseSubmissions(raw));
});
test("actual detail and grade route handlers reject invalid IDs before networking", async () => {
  for (const quizId of ["invalid", "../attempts", "https://example.invalid", id(1) + "/grade"]) {
    assert.equal((await detailRoute(new Request("http://localhost"), { params: Promise.resolve({ quizId }) })).status, 400);
    assert.equal((await gradeRoute(request({ submissions: [] }), { params: Promise.resolve({ quizId }) })).status, 400);
  }
});
test("missing and invalid configuration fail safely without fetching", async () => {
  const fetcher: typeof fetch = async () => { throw new Error("must not fetch"); };
  for (const baseUrl of ["", "not-url", "ftp://example.invalid", "http://user:secret@example.invalid", "http://example.invalid/private", "http://example.invalid/?secret=1"]) {
    const res = await quizApi("catalog", undefined, undefined, { baseUrl, fetcher });
    assert.equal(res.status, 503);
    assert.doesNotMatch(await res.text(), /secret|example\.invalid/);
  }
});
test("catalog/detail use fixed GET endpoints, no cookies, no caching and strip unknown fields", async () => {
  for (const operation of ["catalog", "detail"] as const) {
    const fetcher: typeof fetch = async (url, init) => {
      assert.equal(String(url), `http://127.0.0.1:8000/api/v1/quizzes${operation === "catalog" ? "" : `/${id(1)}`}`);
      assert.equal(init?.method, "GET");
      assert.equal(init?.cache, "no-store");
      assert.equal(init?.redirect, "error");
      assert.equal(new Headers(init?.headers).has("authorization"), false);
      return response(operation === "catalog" ? [{ ...summary, private: "hidden" }] : { ...quiz, private: "hidden" });
    };
    const res = await quizApi(operation, id(1), undefined, { ...configured, fetcher });
    assert.equal(res.status, 200);
    assert.equal(res.headers.get("Cache-Control"), "no-store");
    assert.doesNotMatch(await res.text(), /hidden/);
  }
});
test("grade forwards exact stateless payload and strips unexpected response fields", async () => {
  const payload = { submissions: [{ question_id: id(10), selected_choice_ids: [id(12)] }] };
  const fetcher: typeof fetch = async (url, init) => {
    assert.equal(String(url), `http://127.0.0.1:8000/api/v1/quizzes/${id(1)}/grade`);
    assert.equal(init?.method, "POST");
    assert.deepEqual(JSON.parse(String(init?.body)), payload);
    return response({ ...grade, answer_key: "hidden" });
  };
  const res = await quizApi("grade", id(1), request(payload), { ...configured, fetcher });
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), grade);
});
test("malformed request is rejected before upstream call", async () => {
  const res = await quizApi("grade", id(1), request({ submissions: [{ question_id: id(10), selected_choice_ids: [] }] }), configured);
  assert.equal(res.status, 400);
});
for (const status of [404, 422, 500])
  test(`upstream ${status} is mapped without raw errors`, async () => {
    const res = await quizApi("detail", id(1), undefined, { ...configured, fetcher: async () => response({ detail: "http://private.invalid/secret" }, status) });
    assert.equal(res.status, status === 500 ? 503 : status);
    assert.doesNotMatch(await res.text(), /private|secret/);
  });
test("network errors are controlled", async () => {
  const res = await quizApi("catalog", undefined, undefined, { ...configured, fetcher: async () => { throw new Error("secret"); } });
  assert.equal(res.status, 503);
  assert.doesNotMatch(await res.text(), /secret/);
});
test("timeout aborts upstream with controlled 504", async () => {
  const fetcher: typeof fetch = async (_url, init) => new Promise((_resolve, reject) => init?.signal?.addEventListener("abort", () => reject(new Error("aborted")), { once: true }));
  const res = await quizApi("catalog", undefined, undefined, { ...configured, fetcher, timeoutMs: 5 });
  assert.equal(res.status, 504);
});
test("malformed JSON, unexpected shapes and mismatched quiz IDs fail closed", async () => {
  for (const upstream of [new Response("oops", { headers: { "Content-Type": "application/json" } }), response({}), new Response("html"), response({ ...quiz, quiz_id: id(99) })]) {
    assert.equal((await quizApi("detail", id(1), undefined, { ...configured, fetcher: async () => upstream })).status, 502);
  }
});
