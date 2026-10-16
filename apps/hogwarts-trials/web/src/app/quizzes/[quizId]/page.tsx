import { QuizPlayer } from "../../../components/quiz-player.tsx";
export default async function QuizPage({ params }: {
  params: Promise<{
    quizId: string;
  }>;
}) {
  const { quizId } = await params;
  return <main id="main-content">
    <QuizPlayer key={quizId} quizId={quizId} />
  </main>;
}
