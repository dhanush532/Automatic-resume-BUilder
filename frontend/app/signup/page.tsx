import { AuthShell } from "@/components/auth/auth-shell";
import { SignupForm } from "@/components/auth/signup-form";

export default function SignupPage() {
  return <AuthShell title="Create your account" description="Save your strongest drafts and keep your next opportunity within reach."><SignupForm /></AuthShell>;
}
