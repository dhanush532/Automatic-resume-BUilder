"use client";

import { LogOut, MonitorSmartphone, RefreshCcw, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import Link from "next/link";

import { AuthAlert } from "@/components/auth/auth-alert";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiRequest, type PublicUser, type SecurityEvent, type SessionSummary } from "@/lib/api";

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export function SecurityCenter() {
  const [user, setUser] = useState<PublicUser>();
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [events, setEvents] = useState<SecurityEvent[]>([]);
  const [error, setError] = useState<string>();
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    setError(undefined);
    try {
      const [currentUser, currentSessions, securityEvents] = await Promise.all([
        apiRequest<PublicUser>("/auth/me"), apiRequest<SessionSummary[]>("/auth/sessions"), apiRequest<SecurityEvent[]>("/auth/security-events"),
      ]);
      setUser(currentUser);
      setSessions(currentSessions);
      setEvents(securityEvents);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load security settings.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  async function act(path: string) {
    try {
      await apiRequest(path, { method: "POST" });
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to update sessions.");
    }
  }

  if (loading) return <main className="grid min-h-screen place-items-center text-sm text-muted">Loading security settings…</main>;
  if (!user) return <main className="grid min-h-screen place-items-center px-5"><div className="max-w-md"><AuthAlert tone="info">{error ?? "Sign in to manage your security settings."}</AuthAlert></div></main>;

  return (
    <main className="min-h-screen bg-surface px-5 py-8 sm:px-8">
      <div className="mx-auto max-w-4xl">
        <header className="flex items-start justify-between gap-4 border-b border-line pb-6"><div><p className="text-sm font-medium text-brand">Account</p><h1 className="mt-1 text-3xl font-semibold tracking-tight text-ink">Security settings</h1><p className="mt-2 text-sm text-muted">Signed in as {user.email}</p></div><Button variant="secondary" onClick={() => void act("/auth/logout")}><LogOut className="size-4" />Sign out</Button></header>
        <Link href="/settings/account" className="mt-5 inline-block text-sm text-brand underline">Profile, email, password and connected accounts</Link>
        <div className="mt-8 space-y-6">
          {error && <AuthAlert>{error}</AuthAlert>}
          <Card className="p-6"><div className="flex items-start justify-between gap-4"><div><div className="flex items-center gap-2"><ShieldCheck className="size-5 text-brand" /><h2 className="font-semibold text-ink">Email verification</h2></div><p className="mt-2 text-sm text-muted">Verification protects sign-in. Delivery setup remains environment-dependent.</p></div><StatusBadge tone={user.email_verified ? "success" : "warning"}>{user.email_verified ? "Verified" : "Pending"}</StatusBadge></div></Card>
          <Card className="overflow-hidden"><div className="flex items-center justify-between border-b border-line px-6 py-5"><div><h2 className="font-semibold text-ink">Active sessions</h2><p className="mt-1 text-sm text-muted">Review devices with access to your account.</p></div><Button variant="secondary" onClick={() => void act("/auth/sessions/logout-others")}><RefreshCcw className="size-4" />Log out others</Button></div><div className="divide-y divide-line">{sessions.map((session) => <div className="flex items-center justify-between gap-5 px-6 py-5" key={session.id}><div className="flex min-w-0 gap-3"><MonitorSmartphone className="mt-0.5 size-5 shrink-0 text-muted" /><div><p className="font-medium text-ink">{session.browser ?? "Unknown browser"} on {session.operating_system ?? "unknown system"} {session.current && <span className="ml-2 text-xs font-medium text-brand">Current session</span>}</p><p className="mt-1 text-sm text-muted">{session.ip_address ?? "IP unavailable"} · Last active {formatDate(session.last_active_at)}</p></div></div>{session.current ? <StatusBadge tone="success">Current</StatusBadge> : <Button variant="ghost" onClick={async () => { await apiRequest(`/auth/sessions/${session.id}`, { method: "DELETE" }); await load(); }}>Revoke</Button>}</div>)}</div></Card>
          <Card className="overflow-hidden"><div className="border-b border-line px-6 py-5"><h2 className="font-semibold text-ink">Recent security activity</h2><p className="mt-1 text-sm text-muted">The latest 50 account-security events.</p></div>{events.length ? <ul className="divide-y divide-line">{events.map((event) => <li className="flex justify-between gap-4 px-6 py-4 text-sm" key={event.id}><span className="font-medium text-ink">{event.event_type.replaceAll("_", " ")}</span><span className="text-right text-muted">{formatDate(event.created_at)}{event.ip_address ? ` · ${event.ip_address}` : ""}</span></li>)}</ul> : <p className="px-6 py-8 text-sm text-muted">No security activity recorded yet.</p>}</Card>
        </div>
      </div>
    </main>
  );
}
