"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ArrowUpRight, Command, LogOut, Menu, X } from "lucide-react";
import { useEffect, useState } from "react";
import { apiRequest, type PublicUser } from "@/lib/api";

const links = [["/review", "Resume check"], ["/resumes", "My resumes"], ["/passport", "Career profile"], ["/jobs", "Find jobs"]];

export function SiteHeader() {
  const path = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [user, setUser] = useState<PublicUser | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    void apiRequest<PublicUser>("/auth/me", { signal: controller.signal }).then(setUser).catch(() => {});
    return () => controller.abort();
  }, []);
  async function signOut() {
    setBusy(true); setError("");
    try { await apiRequest("/auth/logout", { method: "POST" }); setUser(null); setOpen(false); router.push("/"); router.refresh(); }
    catch { setError("Could not sign out. Please try again."); }
    finally { setBusy(false); }
  }
  return <header className="site-header">
    <Link href="/" className="wordmark" aria-label="CareerPilot home"><span className="brand-mark"><Command size={20} aria-hidden="true" /></span>careerpilot<span className="brand-dot">.</span></Link>
    <nav aria-label="Main navigation" className="desktop-nav">{links.map(([href, label]) => <Link key={href} href={href} aria-current={path.startsWith(href) ? "page" : undefined}>{label}</Link>)}</nav>
    <div className="header-actions">{user ? <><Link href="/settings/account" className="header-signin">My account</Link><button onClick={() => void signOut()} disabled={busy} aria-label="Sign out" className="header-signin"><LogOut size={16} /></button></> : <Link href="/login" className="header-signin">Sign in</Link>}<Link className="small-cta" href="/review">Check my resume <ArrowUpRight size={15} aria-hidden="true" /></Link><button className="menu-toggle" aria-label={open ? "Close navigation" : "Open navigation"} aria-expanded={open} aria-controls="mobile-navigation" onClick={() => setOpen(!open)}>{open ? <X /> : <Menu />}</button></div>
    {error && <p className="absolute right-4 top-full rounded border border-red-200 bg-white p-3 text-xs text-red-700" role="alert">{error}</p>}
    {open && <nav id="mobile-navigation" aria-label="Mobile navigation" className="mobile-nav">{links.map(([href, label]) => <Link href={href} key={href} onClick={() => setOpen(false)}>{label}</Link>)}{user ? <><Link href="/settings/account" onClick={() => setOpen(false)}>My account</Link><button className="py-4 text-left text-sm" disabled={busy} onClick={() => void signOut()}>Sign out</button></> : <Link href="/login" onClick={() => setOpen(false)}>Sign in</Link>}</nav>}
  </header>;
}
