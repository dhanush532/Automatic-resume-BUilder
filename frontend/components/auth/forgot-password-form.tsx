"use client";

import { FormEvent, useState } from "react";

import { AuthAlert } from "@/components/auth/auth-alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiRequest } from "@/lib/api";

export function ForgotPasswordForm() {
  const [error, setError] = useState<string>();
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string>();

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setError(undefined);
    setMessage(undefined);
    setSubmitting(true);
    try {
      const result = await apiRequest<{message: string}>("/auth/forgot-password", { method: "POST", body: JSON.stringify({ email: form.get("email") }) });
      setMessage(result.message);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to request a reset.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="space-y-5" onSubmit={onSubmit}>
      {error && <AuthAlert tone="info">{error}</AuthAlert>}
      {message && <AuthAlert tone="info">{message}</AuthAlert>}
      <label className="block text-sm font-medium text-ink">Account email<Input autoComplete="email" className="mt-1.5" name="email" required type="email" /></label>
      <Button className="w-full" disabled={submitting} type="submit">{submitting ? "Checking…" : "Send reset link"}</Button>
    </form>
  );
}
