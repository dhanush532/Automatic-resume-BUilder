"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { OtpForm } from "@/components/auth/otp-form";
import { SocialButtons } from "@/components/auth/social-buttons";

import { AuthAlert } from "@/components/auth/auth-alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiRequest, type PublicUser } from "@/lib/api";

export function SignupForm() {
  const [error, setError] = useState<string>();
  const [user, setUser] = useState<PublicUser>();
  const [submitting, setSubmitting] = useState(false);
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [emailAvailable, setEmailAvailable] = useState<boolean | null>(null);
  useEffect(() => { void apiRequest<{email_delivery_configured: boolean}>("/auth/capabilities", { signal: AbortSignal.timeout(8000) }).then(value => setEmailAvailable(value.email_delivery_configured)).catch(() => setEmailAvailable(false)); }, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setError(undefined);
    if (form.get("password") !== form.get("confirm_password")) { setError("Passwords do not match."); return; }
    setSubmitting(true);
    try {
      const result = await apiRequest<PublicUser>("/auth/register", {
        method: "POST",
        body: JSON.stringify({
          full_name: form.get("full_name"), ...(String(form.get("username") ?? "").trim() ? {username: form.get("username")} : {}), email: form.get("email"), phone: form.get("phone") || null, phone_region: form.get("phone_region") || null,
          password: form.get("password"), confirm_password: form.get("confirm_password"), terms_accepted: form.get("terms_accepted") === "on",
        }),
      });
      setUser(result);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to create your account.");
    } finally {
      setSubmitting(false);
    }
  }

  if (user) {
    return <OtpForm initialEmail={user.email} deliveryId={user.delivery_id ?? undefined} initialExpiry={user.verification_expires_at ?? undefined} />;
  }

  return (
    <form className="space-y-4" onSubmit={onSubmit}>
      {error && <AuthAlert>{error}</AuthAlert>}
      <label className="flex items-start gap-3 text-sm leading-5 text-muted"><input className="mt-1 size-4 accent-brand" name="terms_accepted" required type="checkbox" checked={termsAccepted} onChange={(event) => setTermsAccepted(event.target.checked)} /><span>I agree to the <Link href="/terms" className="underline">terms</Link> and <Link href="/privacy" className="underline">privacy policy</Link>.</span></label>
      <SocialButtons termsAccepted={termsAccepted} />
      {!termsAccepted && <p className="text-center text-xs text-muted">Accept the terms above to create an account with your connected login.</p>}
      {emailAvailable === null ? <p className="text-center text-xs text-muted" role="status">Checking email signup availability…</p> : emailAvailable ? <>
      <p className="pt-3 text-center text-xs text-muted">Or create an account with email</p>
      <label className="block text-sm font-medium text-ink">Full name<Input autoComplete="name" className="mt-1.5" name="full_name" required /></label>
      <label className="block text-sm font-medium text-ink">Email<Input autoComplete="email" className="mt-1.5" name="email" required type="email" /></label>
      <label className="block text-sm font-medium text-ink">Password<Input autoComplete="new-password" className="mt-1.5" minLength={12} name="password" required type="password" /><span className="mt-1.5 block text-xs font-normal text-muted">12+ characters, with uppercase, lowercase, number, and symbol.</span></label>
      <label className="block text-sm font-medium text-ink">Confirm password<Input autoComplete="new-password" className="mt-1.5" name="confirm_password" required type="password" /></label>
      <Button className="mt-2 w-full" disabled={submitting} type="submit">{submitting ? "Creating account…" : "Create account"}</Button>
      </> : <p className="rounded-lg border border-line p-3 text-center text-xs leading-6 text-muted">Email signup is currently unavailable. Use an available sign-in option above, or <Link href="/review" className="font-semibold text-brand underline">check your resume without an account</Link>.</p>}
      <p className="text-center text-sm text-muted">Already have an account? <Link className="font-medium text-brand hover:underline" href="/login">Sign in</Link></p>
    </form>
  );
}
