import { quizApi } from "../../../../../quiz/server/quiz-api.ts";
export async function POST(request: Request, context: {
  params: Promise<{
    quizId: string;
  }>;
}) {
  return quizApi("grade", (await context.params).quizId, request);
}
