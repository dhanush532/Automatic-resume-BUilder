"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { AuthAlert } from "@/components/auth/auth-alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiRequest } from "@/lib/api";

type TokenFormMode = "verify" | "reset";

export function TokenForm({ mode }: Readonly<{ mode: TokenFormMode }>) {
  const [error, setError] = useState<string>();
  const [success, setSuccess] = useState<string>();
  const [submitting, setSubmitting] = useState(false);
  const verification = mode === "verify";
  const [resetToken, setResetToken] = useState("");
  useEffect(() => { const token = new URLSearchParams(window.location.hash.slice(1)).get("token"); if (token) { setResetToken(token); window.history.replaceState(null, "", window.location.pathname); } }, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setError(undefined);
    setSuccess(undefined);
    setSubmitting(true);
    try {
      if (verification) {
        await apiRequest("/auth/verify-email", { method: "POST", body: JSON.stringify({ token: form.get("token") }) });
        setSuccess("Email address verified. You can now sign in.");
      } else {
        await apiRequest("/auth/reset-password", {
          method: "POST",
          body: JSON.stringify({ token: form.get("token"), password: form.get("password"), confirm_password: form.get("confirm_password") }),
        });
        setSuccess("Password updated. You can now sign in with your new password.");
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to complete that request.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="space-y-5" onSubmit={onSubmit}>
      {error && <AuthAlert>{error}</AuthAlert>}
      {success && <AuthAlert tone="success">{success}</AuthAlert>}
      <label className="block text-sm font-medium text-ink">{verification ? "Verification token" : "Reset token"}<Input className="mt-1.5" name="token" value={resetToken} onChange={(event) => setResetToken(event.target.value)} required /></label>
      {!verification && <><label className="block text-sm font-medium text-ink">New password<Input autoComplete="new-password" className="mt-1.5" minLength={12} name="password" required type="password" /></label><label className="block text-sm font-medium text-ink">Confirm new password<Input autoComplete="new-password" className="mt-1.5" name="confirm_password" required type="password" /></label></>}
      <Button className="w-full" disabled={submitting} type="submit">{submitting ? "Working…" : verification ? "Verify email" : "Reset password"}</Button>
      {success && <p className="text-center text-sm"><Link className="font-medium text-brand hover:underline" href="/login">Go to sign in</Link></p>}
    </form>
  );
}
