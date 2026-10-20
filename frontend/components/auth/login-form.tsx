"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { SocialButtons } from "@/components/auth/social-buttons";

import { AuthAlert } from "@/components/auth/auth-alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiRequest, type PublicUser } from "@/lib/api";

export function LoginForm() {
  const [error, setError] = useState<string>();
  const [user, setUser] = useState<PublicUser>();
  const [submitting, setSubmitting] = useState(false);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const errorCode = params.get("oauth_error");
    const reasons: Record<string, string> = {
      session_expired: "Your sign-in attempt expired or this browser lost its sign-in cookie. Start again in the same browser tab.",
      access_denied: "Provider sign-in was cancelled. You can try again when you’re ready.",
      verified_email_required: "Your provider did not share a verified email address. Verify an email in your provider account, then try again.",
      provider_configuration: "This sign-in provider could not complete the connection. Please use another sign-in method while its configuration is checked.",
      provider_unavailable: "The sign-in provider is temporarily unavailable. Please wait a moment and try again.",
      account_unavailable: "This account cannot sign in right now. Use your existing login method or contact the site operator.",
    };
    if (errorCode) setError(errorCode === "link_existing_account" ? "Sign in to your existing account, then connect this provider in Account settings." : reasons[params.get("reason") ?? ""] ?? "Social authentication could not be completed. Try again or use your existing login method.");
  }, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setError(undefined);
    setSubmitting(true);
    try {
      const result = await apiRequest<PublicUser>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ identifier: form.get("identifier"), password: form.get("password") }),
      });
      setUser(result);
      let destination = "/resumes";
      try { if (sessionStorage.getItem("careerpilot-review-draft")) destination = "/review"; } catch {}
      window.location.assign(destination);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to sign in.");
    } finally {
      setSubmitting(false);
    }
  }

  if (user) {
    return (
      <div className="space-y-5">
        <AuthAlert tone="success">Welcome back, {user.full_name}. Opening your workspace…</AuthAlert>
        <Button className="w-full" asChild><Link href="/resumes">Open my resumes</Link></Button>
      </div>
    );
  }

  return (
    <form className="space-y-5" onSubmit={onSubmit}>
      {error && <AuthAlert>{error}</AuthAlert>}
      <label className="block text-sm font-medium text-ink">Email or username<Input autoComplete="username" className="mt-1.5" name="identifier" required /></label>
      <label className="block text-sm font-medium text-ink">Password<Input autoComplete="current-password" className="mt-1.5" name="password" required type="password" /></label>
      <div className="flex justify-end"><Link className="text-sm font-medium text-brand hover:underline" href="/forgot-password">Forgot password?</Link></div>
      <Button className="w-full" disabled={submitting} type="submit">{submitting ? "Signing in…" : "Sign in"}</Button>
      <p className="text-center text-xs leading-6 text-muted">By continuing with a provider, you agree to our <Link href="/terms" className="underline">terms</Link> and <Link href="/privacy" className="underline">privacy policy</Link>. We’ll create an account if you’re new.</p>
      <SocialButtons termsAccepted />
      <p className="text-center text-sm text-muted">New to CareerPilot? <Link className="font-medium text-brand hover:underline" href="/signup">Create an account</Link></p>
    </form>
  );
}
