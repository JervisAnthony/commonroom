import { quizApi } from "../../../../quiz/server/quiz-api.ts";
export async function GET(_request: Request, context: {
  params: Promise<{
    quizId: string;
  }>;
}) {
  return quizApi("detail", (await context.params).quizId);
}
