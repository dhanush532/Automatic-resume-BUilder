import Link from "next/link";
import { ArrowUpRight, Command, LockKeyhole } from "lucide-react";

function Brand() {
  return <Link href="/" className="wordmark" aria-label="CareerPilot home"><span className="brand-mark"><Command size={20} aria-hidden="true" /></span>careerpilot<span className="brand-dot">.</span></Link>;
}

export function AuthShell({ title, description, children }: Readonly<{ title: string; description: string; children: React.ReactNode }>) {
  return <main className="auth-surface auth-layout">
    <aside className="auth-story">
      <Brand />
      <div className="auth-story-copy">
        <span className="auth-story-icon"><LockKeyhole size={21} aria-hidden="true" /></span>
        <h2>Less admin.<br />More possibility.</h2>
        <p>Save your strongest drafts, keep your versions together, and be ready for your next opportunity. Start with your existing resume, not an empty form.</p>
        <Link href="/review">Check a resume first <ArrowUpRight size={16} aria-hidden="true" /></Link>
      </div>
      <p>YOUR EXPERIENCE. YOUR NEXT CHAPTER.</p>
    </aside>
    <section className="auth-form-region" aria-label={title}>
      <div className="auth-form-card">
        <div className="auth-mobile-brand"><Brand /></div>
        <h1>{title}</h1>
        <p className="auth-description">{description}</p>
        <div className="auth-form-content">{children}</div>
        <footer className="auth-form-footer"><Link href="/">Back to home</Link><Link href="/privacy">Privacy</Link><Link href="/terms">Terms</Link></footer>
      </div>
    </section>
  </main>;
}
