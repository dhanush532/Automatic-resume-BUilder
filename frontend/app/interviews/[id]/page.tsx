import InterviewRoom from "@/components/interviews/interview-room";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <InterviewRoom id={id} />;
}
