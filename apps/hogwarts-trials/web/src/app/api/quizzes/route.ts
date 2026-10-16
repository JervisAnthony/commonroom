import { quizApi } from "../../../quiz/server/quiz-api.ts";
export const dynamic = "force-dynamic";
export async function GET() { return quizApi("catalog"); }
