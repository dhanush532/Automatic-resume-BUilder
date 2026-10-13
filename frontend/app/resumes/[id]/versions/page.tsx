import { ResumeVersionsPage } from "@/components/resumes/resume-editor-page";

export default async function ResumeVersionsRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ResumeVersionsPage resumeId={id} />;
}
