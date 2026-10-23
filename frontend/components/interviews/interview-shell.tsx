import Link from "next/link";
import type { ReactNode } from "react";
import { ArrowLeft } from "lucide-react";

export function InterviewShell({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return <main className="min-h-[100dvh] bg-[#f3f5ef] px-5 py-8 sm:px-8 lg:px-12"><div className="mx-auto max-w-6xl">
    <Link className="inline-flex min-h-11 items-center gap-2 text-sm text-brand" href="/interviews"><ArrowLeft size={16} aria-hidden />Interview studio</Link>
    <header className="mb-8 mt-4"><p className="text-xs font-semibold uppercase tracking-[.18em] text-brand">CareerPilot / Practice with purpose</p><h1 className="mt-3 text-3xl font-semibold tracking-tight text-brand sm:text-4xl">{title}</h1><p className="mt-3 max-w-2xl text-sm leading-7 text-muted">{description}</p></header>{children}
  </div></main>;
}
export function InterviewError({ children }: { children: ReactNode }) {
  return <div role="alert" className="my-5 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm leading-6 text-rose-800">{children}</div>;
}
