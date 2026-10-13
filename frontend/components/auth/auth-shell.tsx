import Link from "next/link";
import { LockKeyhole } from "lucide-react";

export function AuthShell({
  title,
  description,
  children,
}: Readonly<{ title: string; description: string; children: React.ReactNode }>) {
  return (
    <main className="auth-surface grid min-h-screen bg-surface lg:grid-cols-[.9fr_1.1fr]">
      <aside className="hidden bg-ink px-12 py-10 text-white lg:flex lg:flex-col">
        <Link className="flex items-center gap-2 text-base font-semibold" href="/">
          <span className="grid size-8 place-items-center rounded-lg bg-white text-sm font-bold text-ink">C</span>
          CareerPilot
        </Link>
        <div className="my-auto max-w-sm">
          <div className="grid size-11 place-items-center rounded-lg bg-white/10 text-indigo-200"><LockKeyhole className="size-5" /></div>
          <h2 className="mt-6 text-3xl font-semibold tracking-tight">Your career record stays yours.</h2>
          <p className="mt-4 text-sm leading-7 text-slate-300">CareerPilot hashes passwords and keeps session tokens in HTTP-only cookies. Your email verification and connected login methods protect the same account.</p>
        </div>
        <p className="text-sm text-slate-400">CareerPilot · Private career workspace</p>
      </aside>
      <section className="flex items-center justify-center px-5 py-10 sm:px-8">
        <div className="w-full max-w-md">
          <Link className="mb-12 flex items-center gap-2 font-semibold text-ink lg:hidden" href="/">
            <span className="grid size-8 place-items-center rounded-lg bg-brand text-sm font-bold text-white">C</span>
            CareerPilot
          </Link>
          <h1 className="text-3xl font-semibold tracking-tight text-ink">{title}</h1>
          <p className="mt-3 text-sm leading-6 text-muted">{description}</p>
          <div className="mt-8">{children}</div>
        </div>
      </section>
    </main>
  );
}
