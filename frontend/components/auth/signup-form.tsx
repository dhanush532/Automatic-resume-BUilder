"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
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
      <label className="block text-sm font-medium text-ink">Full name<Input autoComplete="name" className="mt-1.5" name="full_name" required /></label>
      <label className="block text-sm font-medium text-ink">Username (optional)<Input autoComplete="username" className="mt-1.5" name="username" pattern="[A-Za-z0-9._-]{3,30}" /><span className="mt-1 block text-xs font-normal text-muted">We will generate one if you leave this blank.</span></label>
      <label className="block text-sm font-medium text-ink">Email<Input autoComplete="email" className="mt-1.5" name="email" required type="email" /></label>
      <div className="grid gap-3 sm:grid-cols-[1fr_1.5fr]"><label className="block text-sm font-medium text-ink">Phone country<select name="phone_region" defaultValue="IN" className="mt-1.5 h-11 w-full rounded-lg border border-line bg-white px-3 text-sm"><option value="IN">India (+91)</option><option value="US">United States (+1)</option><option value="GB">United Kingdom (+44)</option><option value="CA">Canada (+1)</option><option value="AU">Australia (+61)</option><option value="DE">Germany (+49)</option><option value="">Other (include +country code)</option></select></label><label className="block text-sm font-medium text-ink">Phone number (optional)<Input autoComplete="tel" className="mt-1.5" name="phone" placeholder="10-digit number or +country code" type="tel" /></label></div>
      <label className="block text-sm font-medium text-ink">Password<Input autoComplete="new-password" className="mt-1.5" minLength={12} name="password" required type="password" /><span className="mt-1.5 block text-xs font-normal text-muted">12+ characters, with uppercase, lowercase, number, and symbol.</span></label>
      <label className="block text-sm font-medium text-ink">Confirm password<Input autoComplete="new-password" className="mt-1.5" name="confirm_password" required type="password" /></label>
      <label className="flex items-start gap-3 text-sm leading-5 text-muted"><input className="mt-1 size-4 accent-brand" name="terms_accepted" required type="checkbox" checked={termsAccepted} onChange={(event) => setTermsAccepted(event.target.checked)} />I agree to the terms and privacy policy.</label>
      <Button className="mt-2 w-full" disabled={submitting} type="submit">{submitting ? "Creating account…" : "Create account"}</Button>
      <SocialButtons termsAccepted={termsAccepted} />
      <p className="text-center text-sm text-muted">Already have an account? <Link className="font-medium text-brand hover:underline" href="/login">Sign in</Link></p>
    </form>
  );
}
