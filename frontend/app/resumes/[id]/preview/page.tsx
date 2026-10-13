import { ResumePreviewPage } from "@/components/resumes/resume-editor-page";

export default async function ResumePreviewRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ResumePreviewPage resumeId={id} />;
}
