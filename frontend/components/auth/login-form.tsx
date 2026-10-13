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
  useEffect(() => { const errorCode = new URLSearchParams(window.location.search).get("oauth_error"); if (errorCode) setError(errorCode === "link_existing_account" ? "Sign in to your existing account, then connect this provider in Account settings." : "Social authentication could not be completed. Try again or use your existing login method."); }, []);

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
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to sign in.");
    } finally {
      setSubmitting(false);
    }
  }

  if (user) {
    return (
      <div className="space-y-5">
        <AuthAlert tone="success">Signed in as {user.full_name}. Your server-side session is active.</AuthAlert>
        <Button className="w-full" onClick={() => { window.location.href = "/passport"; }}>Open Career Passport</Button>
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
      <SocialButtons />
      <p className="text-center text-sm text-muted">New to CareerPilot? <Link className="font-medium text-brand hover:underline" href="/signup">Create an account</Link></p>
    </form>
  );
}
