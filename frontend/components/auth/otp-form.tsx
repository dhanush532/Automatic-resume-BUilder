"use client";
import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { apiRequest, type PublicUser } from "@/lib/api";
import { AuthAlert } from "@/components/auth/auth-alert";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export function OtpForm({ initialEmail = "", deliveryId, initialExpiry }: { initialEmail?: string; deliveryId?: string; initialExpiry?: string }) {
  const [email, setEmail] = useState(initialEmail);
  const [delivery, setDelivery] = useState(deliveryId);
  const [expires, setExpires] = useState(initialExpiry);
  const [cooldown, setCooldown] = useState(deliveryId ? 60 : 0);
  const [remaining, setRemaining] = useState<number>();
  const [message, setMessage] = useState<string>();
  const [error, setError] = useState<string>();
  const [success, setSuccess] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => { const timer = setInterval(() => { setCooldown((value) => Math.max(0, value - 1)); if (expires) setRemaining(Math.max(0, Math.ceil((new Date(expires).getTime() - Date.now()) / 1000))); }, 1000); return () => clearInterval(timer); }, [expires]);
  useEffect(() => {
    if (!delivery || success) return;
    let active = true;
    const check = () => apiRequest<{status: string; message: string; expires_at: string; retry_after: number}>(`/auth/email-delivery/${delivery}`).then((value) => {
      if (active) { setMessage(value.message); setExpires(value.expires_at); }
    }).catch(() => { if (active) setMessage("Delivery status could not be checked. You can request another code after the cooldown."); });
    void check(); const timer = setInterval(() => void check(), 5000);
    return () => { active = false; clearInterval(timer); };
  }, [delivery, success]);
  async function verify(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(undefined);
    const form = new FormData(event.currentTarget);
    try { await apiRequest<PublicUser>("/auth/verify-email", {method: "POST", body: JSON.stringify({email: email.trim(), code: form.get("code")})}); setSuccess(true); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to verify this code."); }
    finally { setBusy(false); }
  }
  async function resend() {
    setBusy(true); setError(undefined);
    try { const value = await apiRequest<{delivery_id?: string; expires_at?: string; message: string}>("/auth/resend-verification", {method: "POST", body: JSON.stringify({email: email.trim()})}); setDelivery(value.delivery_id); setExpires(value.expires_at); setMessage(value.message); setCooldown(60); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to request another code."); }
    finally { setBusy(false); }
  }
  if (success) return <div className="space-y-4"><AuthAlert tone="success">Email verified. You can now sign in.</AuthAlert><Button asChild className="w-full"><Link href="/login">Sign in</Link></Button></div>;
  return <form onSubmit={verify} className="space-y-4">
    {message && <AuthAlert tone="info">{message}</AuthAlert>}{error && <AuthAlert>{error}</AuthAlert>}
    <label className="block text-sm font-medium text-ink">Email<Input name="email" autoComplete="email" type="email" required value={email} onChange={(event) => setEmail(event.target.value)} className="mt-2" /></label>
    <label className="block text-sm font-medium text-ink">Six-digit verification code<Input name="code" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" minLength={6} maxLength={6} required className="mt-2 text-center text-xl tracking-widest" /></label>
    {remaining != null && <p className="text-sm text-muted">{remaining > 0 ? `Code expires in ${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, "0")}` : "Code expired. Request another code."}</p>}
    <Button type="submit" className="w-full" disabled={busy || remaining === 0}>{busy ? "Working…" : "Verify email"}</Button>
    <Button type="button" variant="secondary" className="w-full" disabled={busy || cooldown > 0 || !email} onClick={() => void resend()}>{cooldown > 0 ? `Resend in ${cooldown}s` : "Resend code"}</Button>
    <p className="text-xs leading-5 text-muted">Verify in the same browser where you registered. If this browser no longer has your registration, <Link href="/signup" className="text-brand underline">restart registration</Link>. Never share your code.</p>
  </form>;
}
