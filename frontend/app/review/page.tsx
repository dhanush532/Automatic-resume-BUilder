import type { Metadata } from "next";
import { ReviewWorkspace } from "@/components/review/review-workspace";

export const metadata: Metadata = { title: "Check your resume · CareerPilot", description: "Upload a resume, get evidence-based feedback, and improve it without a lengthy form." };
export default function ReviewPage() { return <ReviewWorkspace />; }
