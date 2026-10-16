// Imported only by route handlers. No backend configuration enters client modules.
import { isUuid, parseCatalog, parseGrade, parseQuiz, parseSubmissions } from "../quiz-contract.ts";
type Operation = "catalog" | "detail" | "grade";
const errors = {
  400: "Invalid quiz identifier or submission.",
  404: "This trial could not be found. Return to the catalog to choose another.",
  422: "The service could not accept these answers. Review your selections and try again.",
  502: "The quiz service returned an unexpected response. Please try again.",
  503: "The quiz service is unavailable. Please try again shortly.",
  504: "The quiz service took too long to respond. Please try again.",
};
function error(status: keyof typeof errors) { return Response.json({ error: errors[status] }, { status, headers: { "Cache-Control": "no-store" } }); }
export async function quizApi(operation: Operation, quizId?: string, request?: Request, options: {
  baseUrl?: string;
  fetcher?: typeof fetch;
  timeoutMs?: number;
} = {}): Promise<Response> {
  if (operation !== "catalog" && !isUuid(quizId))
    return error(400);
  let body: string | undefined;
  if (operation === "grade") {
    try {
      body = JSON.stringify(parseSubmissions(await request?.json()));
    }
    catch {
      return error(400);
    }
  }
  const configured = options.baseUrl ?? process.env.HOGWARTS_TRIALS_API_URL;
  if (!configured)
    return Response.json({ error: "The quiz service is not configured. Set HOGWARTS_TRIALS_API_URL on the web server, then restart it." }, { status: 503, headers: { "Cache-Control": "no-store" } });
  let origin: URL;
  try {
    origin = new URL(configured);
    if (!["http:", "https:"].includes(origin.protocol) || origin.username || origin.password || origin.search || origin.hash || origin.pathname !== "/")
      return error(503);
  }
  catch {
    return error(503);
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), options.timeoutMs ?? 8000);
  try {
    const path = `/api/v1/quizzes${operation === "catalog" ? "" : `/${quizId!.toLowerCase()}${operation === "grade" ? "/grade" : ""}`}`;
    const response = await (options.fetcher ?? fetch)(new URL(path, origin), { method: operation === "grade" ? "POST" : "GET", body, headers: { Accept: "application/json", ...(body ? { "Content-Type": "application/json" } : {}) }, cache: "no-store", redirect: "error", signal: controller.signal });
    if (!response.ok)
      return error(response.status === 404 ? 404 : response.status === 422 ? 422 : 503);
    if (!response.headers.get("content-type")?.includes("application/json"))
      return error(502);
    let data;
    try {
      const raw: unknown = await response.json();
      data = operation === "catalog" ? parseCatalog(raw) : operation === "detail" ? parseQuiz(raw) : parseGrade(raw);
      if (operation !== "catalog" && "quiz_id" in data && data.quiz_id !== quizId!.toLowerCase())
        return error(502);
    }
    catch {
      return controller.signal.aborted ? error(504) : error(502);
    }
    return Response.json(data, { headers: { "Cache-Control": "no-store" } });
  }
  catch {
    return error(controller.signal.aborted ? 504 : 503);
  }
  finally {
    clearTimeout(timer);
  }
}
