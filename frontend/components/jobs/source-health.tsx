"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ApiError, apiRequest } from "@/lib/api";

type SourceHealth = {
  source_key: string;
  name: string;
  configured: boolean;
  enabled: boolean;
  last_success_at: string | null;
  last_error: string | null;
  last_job_count: number | null;
};

export function SourceHealthNotice() {
  const [sources, setSources] = useState<SourceHealth[]>([]);
  const [message, setMessage] = useState("Checking source availability…");

  useEffect(() => {
    let active = true;
    apiRequest<SourceHealth[]>("/jobs/sources").then((result) => {
      if (!active) return;
      setSources(result);
      setMessage(result.some((source) => source.enabled) ? "" : "Live ingestion is disabled. Previously collected listings may remain until they become stale.");
    }).catch((error) => {
      if (active) setMessage(error instanceof ApiError && error.status === 401 ? "Sign in to browse jobs and view source health." : "Source health could not be checked.");
    });
    return () => { active = false; };
  }, []);

  return <section aria-label="Job source health" className="mt-5 rounded-lg border border-line bg-white p-4 text-sm text-muted">
    <p>Job data from <a className="font-medium text-brand underline" href="https://www.arbeitnow.com" target="_blank" rel="noopener noreferrer">Arbeitnow</a>. Initial coverage focuses on Germany and Europe; remote does not imply worldwide eligibility.</p>
    {message && <p className="mt-2">{message} {message.startsWith("Sign in") && <Link className="font-medium text-brand underline" href="/login">Sign in</Link>}</p>}
    {sources.filter((source) => source.source_key === "arbeitnow").map((source) => <p className="mt-2" key={source.source_key}>
      {source.name}: {source.enabled ? "enabled" : "disabled"} · {source.last_success_at ? `Last successful sync ${new Date(source.last_success_at).toLocaleString()} (${source.last_job_count ?? 0} listings processed)` : "No successful sync yet"}
      {source.last_error && <span className="block text-amber-800">Latest attempt failed; prior data is retained. Freshness checks still apply.</span>}
    </p>)}
    <p className="mt-2 text-xs">Source checks are not guarantees of employer identity or job legitimacy. CareerPilot never submits an application from this page.</p>
  </section>;
}
