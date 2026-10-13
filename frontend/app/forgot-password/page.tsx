import Link from "next/link";

import { AuthShell } from "@/components/auth/auth-shell";
import { ForgotPasswordForm } from "@/components/auth/forgot-password-form";

export default function ForgotPasswordPage() {
  return <AuthShell title="Reset your password" description="Enter your account email to request a secure, one-time reset link."><ForgotPasswordForm /><p className="mt-5 text-center text-sm text-muted"><Link className="font-medium text-brand hover:underline" href="/login">Back to sign in</Link></p></AuthShell>;
}
