"use client";
import { useCallback, useEffect, useId, useState } from "react";
import { Github, Linkedin, LoaderCircle } from "lucide-react";
import { apiRequest } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { AuthAlert } from "@/components/auth/auth-alert";

const providerNames = ["google", "github", "linkedin"] as const;
type Provider = { name: typeof providerNames[number]; configured: boolean };

function ProviderIcon({ provider }: { provider: string }) {
  if (provider === "github") return <Github className="h-5 w-5" aria-hidden="true" />;
  if (provider === "linkedin") return <Linkedin className="h-5 w-5 text-[#0a66c2]" aria-hidden="true" />;
  return <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden="true">
    <path fill="#4285F4" d="M21.6 12.23c0-.71-.06-1.39-.18-2.05H12v3.88h5.38a4.6 4.6 0 0 1-2 3.02v2.51h3.24c1.9-1.75 2.98-4.32 2.98-7.36Z" />
    <path fill="#34A853" d="M12 22c2.7 0 4.96-.9 6.62-2.41l-3.24-2.51c-.9.6-2.06.96-3.38.96-2.61 0-4.82-1.76-5.61-4.12H3.05v2.59A10 10 0 0 0 12 22Z" />
    <path fill="#FBBC05" d="M6.39 13.92a6 6 0 0 1 0-3.84V7.49H3.05a10 10 0 0 0 0 9.02l3.34-2.59Z" />
    <path fill="#EA4335" d="M12 5.96c1.47 0 2.79.5 3.83 1.5l2.87-2.88A9.6 9.6 0 0 0 12 2a10 10 0 0 0-8.95 5.49l3.34 2.59C7.18 7.72 9.39 5.96 12 5.96Z" />
  </svg>;
}

export function SocialButtons({ mode = "login", connected = [], termsAccepted = false }: { mode?: "login" | "link" | "reauth"; connected?: string[]; termsAccepted?: boolean }) {
  const statusId = useId();
  const [providers, setProviders] = useState<Provider[]>(() => providerNames.map((name) => ({ name, configured: false })));
  const [availability, setAvailability] = useState<"checking" | "ready" | "unavailable">("checking");
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState<string>();
  const checkAvailability = useCallback(async () => {
    setAvailability("checking");
    try {
      const value = await apiRequest<{ providers: Provider[] }>("/auth/capabilities", { signal: AbortSignal.timeout(8000) });
      if (!Array.isArray(value.providers)) throw new Error("Invalid provider availability");
      setProviders(providerNames.map((name) => ({ name, configured: value.providers.some((provider) => provider.name === name && provider.configured === true) })));
      setAvailability("ready");
    } catch {
      setAvailability("unavailable");
    }
  }, []);
  useEffect(() => { void checkAvailability(); }, [checkAvailability]);
  async function start(provider: string) {
    setBusy(provider); setError(undefined);
    try { const result = await apiRequest<{authorization_url: string}>(`/auth/oauth/${provider}/start`, {method: "POST", body: JSON.stringify({mode, terms_accepted: termsAccepted})}); window.location.assign(result.authorization_url); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Could not start provider authentication."); setBusy(undefined); }
  }
  return <div className="space-y-3">{error && <AuthAlert>{error}</AuthAlert>}
    <div className={mode === "login" ? "social-login-grid" : "space-y-3"}>
      {providers.filter((provider) => mode !== "reauth" || connected.includes(provider.name)).map((provider) => {
        const name = provider.name === "github" ? "GitHub" : provider.name === "linkedin" ? "LinkedIn" : "Google";
        const label = `${mode === "link" ? "Connect" : mode === "reauth" ? "Reauthenticate with" : "Continue with"} ${name}`;
        const unavailable = availability === "ready" && !provider.configured;
        const hint = availability === "checking" ? `Checking ${name} availability` : availability === "unavailable" ? `${name}: sign-in temporarily unavailable` : unavailable ? `${name} sign-in is not available yet` : label;
        const noteId = `${statusId}-${provider.name}`;
        return <div key={provider.name} title={hint} className="social-provider">
          <Button type="button" variant="secondary" aria-label={busy === provider.name ? `Redirecting to ${name}` : label}
            aria-describedby={unavailable ? noteId : undefined}
            className={mode === "login" ? "h-20 w-full flex-col gap-2 px-2 text-xs disabled:opacity-100 disabled:bg-surface disabled:text-muted" : "h-12 w-full disabled:opacity-100 disabled:bg-surface disabled:text-muted"}
            disabled={availability !== "ready" || !provider.configured || !!busy || (mode === "link" && connected.includes(provider.name))} onClick={() => void start(provider.name)}>
            {busy === provider.name ? <LoaderCircle className="h-5 w-5 animate-spin" aria-hidden="true" /> : <ProviderIcon provider={provider.name} />}
            {busy === provider.name ? "Redirecting…" : mode === "login" ? name : label}
          </Button>
          {unavailable && <p id={noteId} className="social-provider-note">Not available yet</p>}
        </div>;
      })}
    </div>
    <div aria-live="polite" className="text-center text-xs text-muted">
      {availability === "checking" && <p>Checking social sign-in…</p>}
      {availability === "ready" && !providers.some(provider => provider.configured) && <p>No social sign-in options are currently available.</p>}
      {availability === "unavailable" && <><p>Social sign-in is temporarily unavailable.</p><Button type="button" variant="ghost" className="mt-1 h-8 text-xs" onClick={() => void checkAvailability()}>Retry availability check</Button></>}
    </div>
  </div>;
}
