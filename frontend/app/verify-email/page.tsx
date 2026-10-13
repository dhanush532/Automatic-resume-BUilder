import { AuthShell } from "@/components/auth/auth-shell";
import { OtpForm } from "@/components/auth/otp-form";

export default function VerifyEmailPage() {
  return <AuthShell title="Verify your email" description="Enter the six-digit code sent to your email. Codes expire after five minutes."><OtpForm /></AuthShell>;
}
