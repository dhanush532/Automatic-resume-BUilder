import Link from "next/link";
import { ArrowRight, BriefcaseBusiness, CheckCircle2, FileText, Layers3, LockKeyhole, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";

const foundations = [
  {
    icon: Layers3,
    title: "Career Passport",
    description: "One structured, editable record for the experience and skills you choose to share.",
  },
  {
    icon: FileText,
    title: "Resume workspace",
    description: "Human-designed templates and versioned resumes built from your verified profile data.",
  },
  {
    icon: BriefcaseBusiness,
    title: "Job decisions",
    description: "Source-traceable opportunities, explained matches, and an application history you control.",
  },
];

export default function HomePage() {
  return (
    <main className="min-h-screen px-5 py-5 sm:px-8 sm:py-8 lg:px-12">
      <div className="mx-auto max-w-6xl">
        <header className="flex items-center justify-between border-b border-line pb-5">
          <a className="flex items-center gap-2 font-semibold tracking-tight text-ink" href="#overview">
            <span className="grid size-8 place-items-center rounded-lg bg-brand text-sm font-bold text-white">C</span>
            CareerPilot
          </a>
          <StatusBadge tone="success">Authentication ready</StatusBadge>
        </header>

        <section className="grid gap-8 py-14 lg:grid-cols-[1.15fr_.85fr] lg:items-center lg:py-20" id="overview">
          <div>
            <p className="mb-4 text-sm font-semibold uppercase tracking-[0.16em] text-brand">A calmer way to manage your career</p>
            <h1 className="max-w-3xl text-4xl font-semibold tracking-[-0.04em] text-ink sm:text-5xl">
              Your experience, kept accurate and ready for the right opportunity.
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-muted">
              CareerPilot is being built as a private career workspace. Your Career Passport stays the source of truth; any future assistance is constrained to the information you provide.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Button asChild><Link href="/signup">Create your account <ArrowRight className="size-4" aria-hidden="true" /></Link></Button>
              <Button asChild variant="secondary"><Link href="/login">Sign in</Link></Button>
              <Button asChild variant="ghost"><Link href="/passport">Open Career Passport</Link></Button>
              <Button asChild variant="ghost"><Link href="/resumes">Resume workspace</Link></Button>
              <Button asChild variant="ghost"><Link href="/jobs">Browse jobs</Link></Button>
            </div>
            <p className="mt-3 text-sm text-muted">Authentication, Career Passport, resumes, and the source-traceable job system are ready. Live listings appear only after a legitimate source is configured.</p>
          </div>

          <Card className="overflow-hidden">
            <div className="border-b border-line bg-slate-50 px-6 py-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-ink">Build status</p>
                  <p className="mt-1 text-sm text-muted">What is ready in this release</p>
                </div>
                <CheckCircle2 className="size-5 text-emerald-600" aria-hidden="true" />
              </div>
            </div>
            <div className="space-y-5 px-6 py-6">
              <BuildRow label="Responsive application shell" status="Ready" />
              <BuildRow label="FastAPI health service" status="Ready" />
              <BuildRow label="PostgreSQL migration baseline" status="Ready" />
              <BuildRow label="Authentication and private data" status="Ready" />
              <BuildRow label="Source-traceable job discovery" status="Ready" />
            </div>
          </Card>
        </section>

        <section aria-labelledby="foundation-heading" className="border-t border-line py-12">
          <div className="mb-7 flex items-start justify-between gap-6">
            <div>
              <p className="text-sm font-semibold text-brand">Product foundation</p>
              <h2 id="foundation-heading" className="mt-2 text-2xl font-semibold tracking-tight text-ink">Designed around data ownership</h2>
            </div>
            <LockKeyhole className="mt-1 size-5 shrink-0 text-muted" aria-hidden="true" />
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            {foundations.map(({ icon: Icon, title, description }) => (
              <Card className="p-6" key={title}>
                <div className="grid size-10 place-items-center rounded-lg bg-indigo-50 text-brand"><Icon className="size-5" aria-hidden="true" /></div>
                <h3 className="mt-5 font-semibold text-ink">{title}</h3>
                <p className="mt-2 text-sm leading-6 text-muted">{description}</p>
              </Card>
            ))}
          </div>
        </section>

        <footer className="flex flex-col gap-2 border-t border-line py-6 text-sm text-muted sm:flex-row sm:items-center sm:justify-between">
          <span>CareerPilot · Foundation release</span>
          <span className="flex items-center gap-1.5"><Sparkles className="size-3.5" aria-hidden="true" /> No profile or job data is fabricated.</span>
        </footer>
      </div>
    </main>
  );
}

function BuildRow({ label, status, pending = false }: { label: string; status: string; pending?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-sm text-ink">{label}</span>
      <StatusBadge tone={pending ? "neutral" : "success"}>{status}</StatusBadge>
    </div>
  );
}
