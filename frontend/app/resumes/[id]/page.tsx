import { ResumeEditorPage } from "@/components/resumes/resume-editor-page";

export default async function ResumePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ResumeEditorPage resumeId={id} />;
}
