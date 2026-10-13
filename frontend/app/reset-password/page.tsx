import { AuthShell } from "@/components/auth/auth-shell";
import { TokenForm } from "@/components/auth/token-form";

export default function ResetPasswordPage() {
  return <AuthShell title="Choose a new password" description="Reset links are single-use and expire shortly after they are issued."><TokenForm mode="reset" /></AuthShell>;
}
