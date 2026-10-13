import { JobDetailPage } from "@/components/jobs/jobs-page";

export default async function JobDetailRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <JobDetailPage jobId={id} />;
}
