"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, Bookmark, BookmarkCheck, BriefcaseBusiness, ExternalLink, Search, SlidersHorizontal } from "lucide-react";

import { ApiError, apiRequest } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { StatusBadge } from "@/components/ui/status-badge";
import { SourceHealthNotice } from "@/components/jobs/source-health";

export type JobSkill = { id: string; name: string; is_required: boolean };
export type Company = { id: string; name: string; normalized_name: string; website: string | null; logo_url: string | null; description: string | null; headquarters: string | null };
export type JobSource = { id: string; source_key: string; name: string; source_type: string };
export type Job = { id: string; company: Company; source: JobSource; external_job_id: string | null; title: string; description: string; location: string | null; normalized_location: string | null; remote_type: string; employment_type: string; experience_requirements: string | null; education_requirements: string | null; salary_min: string | number | null; salary_max: string | number | null; salary_currency: string | null; salary_period: string | null; application_url: string; canonical_url: string | null; source_url: string; posted_at: string | null; deadline_at: string | null; first_seen_at: string; last_seen_at: string; last_verified_at: string | null; status: "ACTIVE" | "CLOSED" | "EXPIRED" | "UNVERIFIED"; verification_status: string; application_link_allowed: boolean; verification_reason: string | null; skills: JobSkill[]; is_saved: boolean };
type JobPage = { items: Job[]; page: number; page_size: number; total: number; has_next: boolean };
type Match = { job_id: string; score: number; score_method: string; matching_skills: string[]; missing_skills: string[]; uncertain_skills: string[]; reasons: string[]; conflicts: string[] };
type SkillGaps = { job_id: string; matched_skills: string[]; missing_skills: string[]; uncertain_skills: string[]; normalization_rule: string };
type SavedPage = { items: Array<{ job: Job; saved_at: string }>; page: number; page_size: number; total: number; has_next: boolean };

const remoteLabels: Record<string, string> = { remote: "Remote", hybrid: "Hybrid", onsite: "On-site", unknown: "Remote type unavailable" };
const employmentLabels: Record<string, string> = { full_time: "Full-time", part_time: "Part-time", contract: "Contract", internship: "Internship", temporary: "Temporary", freelance: "Freelance", volunteer: "Volunteer", unknown: "Employment type unavailable" };

function formatDate(value: string | null) {
  if (!value) return "Date unavailable";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value));
}

function formatSalary(job: Job) {
  if (job.salary_min == null && job.salary_max == null) return "Salary not provided";
  const currency = job.salary_currency ?? "";
  const period = job.salary_period ? ` / ${job.salary_period}` : "";
  const minimum = job.salary_min == null ? "" : `${currency} ${Number(job.salary_min).toLocaleString()}`;
  const maximum = job.salary_max == null ? "" : `${currency} ${Number(job.salary_max).toLocaleString()}`;
  return minimum && maximum ? `${minimum} – ${maximum}${period}` : `${minimum || maximum}${period}`;
}

function statusTone(status: Job["status"]): "neutral" | "warning" | "success" {
  return status === "ACTIVE" ? "success" : status === "UNVERIFIED" ? "warning" : "neutral";
}

function statusLabel(status: Job["status"]) {
  return status === "UNVERIFIED" ? "Unverified" : status[0] + status.slice(1).toLowerCase();
}

function ErrorNotice({ error }: { error: string }) {
  return <p className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</p>;
}

function JobCard({ job, onSaved }: { job: Job; onSaved?: (job: Job) => void }) {
  const [saved, setSaved] = useState(job.is_saved);
  const [busy, setBusy] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  async function toggleSaved() {
    setBusy(true);
    setSaveError(null);
    try {
      if (saved) await apiRequest(`/saved-jobs/${job.id}`, { method: "DELETE" });
      else await apiRequest(`/saved-jobs`, { method: "POST", body: JSON.stringify({ job_id: job.id }) });
      setSaved(!saved);
      onSaved?.({ ...job, is_saved: !saved });
    } catch (caught) {
      setSaveError(caught instanceof ApiError ? caught.message : "Could not update saved jobs.");
    } finally {
      setBusy(false);
    }
  }
  return <Card className="p-5 sm:p-6"><div className="flex items-start justify-between gap-4"><div><Link className="text-xl font-semibold text-ink hover:text-brand" href={`/jobs/${job.id}`}>{job.title}</Link><p className="mt-1 text-sm font-medium text-brand">{job.company.name}</p></div><StatusBadge tone={statusTone(job.status)}>{statusLabel(job.status)}</StatusBadge></div><div className="mt-4 flex flex-wrap gap-x-4 gap-y-2 text-sm text-muted"><span>{job.location ?? "Location unavailable"}</span><span>{remoteLabels[job.remote_type] ?? job.remote_type}</span><span>{employmentLabels[job.employment_type] ?? job.employment_type}</span></div><p className="mt-4 line-clamp-3 text-sm leading-6 text-muted">{job.description}</p><div className="mt-4 flex flex-wrap items-center justify-between gap-3"><div className="text-sm font-medium text-ink">{formatSalary(job)}</div><div className="flex gap-2"><Button variant="ghost" onClick={() => void toggleSaved()} disabled={busy}>{saved ? <BookmarkCheck className="size-4" aria-hidden="true" /> : <Bookmark className="size-4" aria-hidden="true" />}{saved ? "Saved" : "Save"}</Button><Button asChild variant="secondary"><Link href={`/jobs/${job.id}`}>View details</Link></Button></div></div><p className="mt-3 text-xs text-muted">Posted {formatDate(job.posted_at)} · Source checked {formatDate(job.last_verified_at)}</p><p className="mt-2 text-xs text-muted">Trust: {job.verification_status.replaceAll("_", " ")} · Source: {job.source.name === "Arbeitnow" ? <a href="https://www.arbeitnow.com" target="_blank" rel="noopener noreferrer" className="underline">Arbeitnow</a> : job.source.name}</p>{saveError && <ErrorNotice error={saveError} />}</Card>;
}

export function JobsPage() {
  const [result, setResult] = useState<JobPage | null>(null);
  const [keyword, setKeyword] = useState("");
  const [location, setLocation] = useState("");
  const [remoteType, setRemoteType] = useState("");
  const [employmentType, setEmploymentType] = useState("");
  const [includeUnverified, setIncludeUnverified] = useState(false);
  const [sort, setSort] = useState("newest");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const query = useMemo(() => ({ keyword, location, remoteType, employmentType, includeUnverified, sort, page }), [keyword, location, remoteType, employmentType, includeUnverified, sort, page]);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    const params = new URLSearchParams({ page: String(query.page), page_size: "10" });
    params.set("sort", query.sort);
    if (query.keyword.trim()) params.set("keyword", query.keyword.trim());
    if (query.location.trim()) params.set("location", query.location.trim());
    if (query.remoteType) params.set("remote_type", query.remoteType);
    if (query.employmentType) params.set("employment_type", query.employmentType);
    if (query.includeUnverified) params.set("include_unverified", "true");
    try { setResult(await apiRequest<JobPage>(`/jobs?${params.toString()}`)); } catch (caught) { setError(caught instanceof ApiError ? caught.message : "Could not load jobs."); } finally { setLoading(false); }
  }, [query]);
  useEffect(() => { void load(); }, [load]);

  function submit(event: React.FormEvent) { event.preventDefault(); setPage(1); void load(); }
  return <main className="min-h-screen bg-slate-50 px-5 py-6 sm:px-8 sm:py-10 lg:px-12"><div className="mx-auto max-w-6xl"><header className="flex flex-col gap-5 border-b border-line pb-7 sm:flex-row sm:items-end sm:justify-between"><div><Link className="inline-flex items-center gap-2 text-sm font-medium text-muted hover:text-ink" href="/"><ArrowLeft className="size-4" aria-hidden="true" />Home</Link><p className="mt-7 text-sm font-semibold uppercase tracking-[0.16em] text-brand">Job discovery</p><h1 className="mt-2 text-3xl font-semibold tracking-[-0.03em] text-ink sm:text-4xl">Find the right next opportunity.</h1><p className="mt-3 max-w-2xl leading-7 text-muted">Only authorized source listings appear here. Every result keeps its source, application link, verification state, and last-seen evidence.</p></div><div className="flex gap-2"><Button asChild variant="secondary"><Link href="/saved-jobs"><Bookmark className="size-4" aria-hidden="true" />Saved jobs</Link></Button><Button asChild variant="ghost"><Link href="/passport">Career Passport</Link></Button></div></header><SourceHealthNotice /><Card className="mt-7 p-5 sm:p-6"><form className="grid gap-4 lg:grid-cols-[1.4fr_1fr_1fr_auto]" onSubmit={submit}><label className="block text-sm font-medium text-ink lg:col-span-1">Keyword<Input className="mt-2" value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="Title, company or skill" /></label><label className="block text-sm font-medium text-ink">Location<Input className="mt-2" value={location} onChange={(event) => setLocation(event.target.value)} placeholder="City or region" /></label><label className="block text-sm font-medium text-ink">Remote type<select className="mt-2 h-11 w-full rounded-lg border border-line bg-white px-3 text-sm text-ink" value={remoteType} onChange={(event) => setRemoteType(event.target.value)}><option value="">Any</option><option value="remote">Remote</option><option value="hybrid">Hybrid</option><option value="onsite">On-site</option></select></label><Button className="self-end" type="submit"><Search className="size-4" aria-hidden="true" />Search</Button></form><div className="mt-4 flex flex-wrap items-center gap-4 border-t border-line pt-4"><label className="text-sm text-muted">Employment type<select className="ml-2 rounded-lg border border-line bg-white px-3 py-2 text-sm text-ink" value={employmentType} onChange={(event) => { setEmploymentType(event.target.value); setPage(1); }}><option value="">Any</option><option value="full_time">Full-time</option><option value="part_time">Part-time</option><option value="contract">Contract</option><option value="internship">Internship</option></select></label><label className="text-sm text-muted">Sort by<select className="ml-2 rounded-lg border border-line bg-white px-3 py-2 text-sm text-ink" value={sort} onChange={(event) => { setSort(event.target.value); setPage(1); }}><option value="newest">Newest</option><option value="oldest">Oldest</option><option value="salary_high">Highest salary</option><option value="salary_low">Lowest salary</option></select></label><label className="flex items-center gap-2 text-sm text-muted"><input type="checkbox" checked={includeUnverified} onChange={(event) => { setIncludeUnverified(event.target.checked); setPage(1); }} />Include unverified listings</label><span className="inline-flex items-center gap-1 text-xs text-muted"><SlidersHorizontal className="size-3.5" aria-hidden="true" />Results are source-filtered and paginated.</span></div></Card>{error && <div className="mt-6"><ErrorNotice error={error} /></div>}{loading ? <Card className="mt-6 p-8 text-sm text-muted">Loading authorized job listings…</Card> : error ? null : result && result.items.length ? <><div className="mt-6 flex items-center justify-between gap-4"><p className="text-sm text-muted">{result.total} {result.total === 1 ? "listing" : "listings"}</p><p className="text-xs text-muted">Page {result.page}</p></div><div className="mt-3 grid gap-4">{result.items.map((job) => <JobCard key={job.id} job={job} />)}</div><Pagination page={result.page} hasNext={result.has_next} onChange={setPage} /></> : <Card className="mt-6 border-dashed p-10 text-center"><BriefcaseBusiness className="mx-auto size-8 text-muted" aria-hidden="true" /><h2 className="mt-4 text-lg font-semibold text-ink">No listings match your filters</h2><p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-muted">Try different filters or check the source status above. Stale and suspicious listings are excluded by default. CareerPilot does not create sample vacancies.</p></Card>}</div></main>;
}

export function Pagination({ page, hasNext, onChange }: { page: number; hasNext: boolean; onChange: (page: number) => void }) {
  return <div className="mt-6 flex justify-center gap-2"><Button variant="secondary" disabled={page <= 1} onClick={() => onChange(page - 1)}>Previous</Button><span className="inline-flex h-10 items-center px-3 text-sm text-muted">Page {page}</span><Button variant="secondary" disabled={!hasNext} onClick={() => onChange(page + 1)}>Next</Button></div>;
}

export function JobDetailPage({ jobId }: { jobId: string }) {
  const [job, setJob] = useState<Job | null>(null);
  const [match, setMatch] = useState<Match | null>(null);
  const [gaps, setGaps] = useState<SkillGaps | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  useEffect(() => { void Promise.all([apiRequest<Job>(`/jobs/${jobId}`), apiRequest<Match>(`/jobs/${jobId}/match`), apiRequest<SkillGaps>(`/jobs/${jobId}/skill-gaps`)]).then(([loaded, loadedMatch, loadedGaps]) => { setJob(loaded); setMatch(loadedMatch); setGaps(loadedGaps); }).catch((caught) => setError(caught instanceof ApiError ? caught.message : "Could not load this job.")).finally(() => setLoading(false)); }, [jobId]);
  async function toggleSaved() { if (!job) return; setSaving(true); try { if (job.is_saved) await apiRequest(`/saved-jobs/${job.id}`, { method: "DELETE" }); else await apiRequest(`/saved-jobs`, { method: "POST", body: JSON.stringify({ job_id: job.id }) }); setJob({ ...job, is_saved: !job.is_saved }); } catch (caught) { setError(caught instanceof ApiError ? caught.message : "Could not update saved jobs."); } finally { setSaving(false); } }
  if (loading) return <JobShell><Card className="p-8 text-sm text-muted">Loading job details…</Card></JobShell>;
  if (error || !job) return <JobShell><ErrorNotice error={error ?? "Job not found."} /></JobShell>;
  return <JobShell><div className="flex flex-wrap items-start justify-between gap-5"><div><StatusBadge tone={statusTone(job.status)}>{statusLabel(job.status)}</StatusBadge><h1 className="mt-4 text-3xl font-semibold tracking-[-0.03em] text-ink sm:text-4xl">{job.title}</h1><p className="mt-2 text-lg font-medium text-brand">{job.company.name}</p><p className="mt-4 text-sm text-muted">{job.location ?? "Location unavailable"} · {remoteLabels[job.remote_type]} · {employmentLabels[job.employment_type]}</p></div><div className="flex flex-wrap gap-2"><Button onClick={() => void toggleSaved()} disabled={saving}>{job.is_saved ? <BookmarkCheck className="size-4" aria-hidden="true" /> : <Bookmark className="size-4" aria-hidden="true" />}{job.is_saved ? "Saved" : "Save job"}</Button>{job.application_link_allowed ? <Button asChild variant="secondary"><a href={job.application_url} target="_blank" rel="noopener noreferrer">View source listing <ExternalLink className="size-4" aria-hidden="true" /></a></Button> : <p className="max-w-xs text-sm text-amber-800">Application link disabled: this listing needs review or is no longer current.</p>}</div></div><div className="mt-8 grid gap-6 lg:grid-cols-[1.2fr_.8fr]"><div className="space-y-6"><Card className="p-6 sm:p-8"><h2 className="text-xl font-semibold text-ink">Description</h2><p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-muted">{job.description}</p></Card><Card className="p-6 sm:p-8"><h2 className="text-xl font-semibold text-ink">Requirements and skills</h2><div className="mt-5 grid gap-5 sm:grid-cols-2"><Info label="Experience" value={job.experience_requirements} /><Info label="Education" value={job.education_requirements} /><Info label="Salary" value={formatSalary(job)} /><Info label="Deadline" value={formatDate(job.deadline_at)} /></div><div className="mt-6 flex flex-wrap gap-2">{job.skills.length ? job.skills.map((skill) => <span className="rounded-full bg-indigo-50 px-3 py-1.5 text-xs font-medium text-brand" key={skill.id}>{skill.name}{skill.is_required ? "" : " · preferred"}</span>) : <p className="text-sm text-muted">Skills were not provided by the source.</p>}</div></Card><Card className="p-6 sm:p-8"><h2 className="text-xl font-semibold text-ink">Verification</h2><div className="mt-5 grid gap-4 sm:grid-cols-2"><Info label="Trust assessment" value={job.verification_status.replaceAll("_", " ")} /><Info label="Source" value={job.source.name} /><Info label="Source URL" value={job.source_url} /><Info label="Source checked" value={formatDate(job.last_verified_at)} /><Info label="Last seen" value={formatDate(job.last_seen_at)} /></div>{job.verification_reason && <p className="mt-5 rounded-lg bg-amber-50 px-3 py-3 text-sm text-amber-900">{job.verification_reason}</p>}<p className="mt-5 text-xs leading-5 text-muted">Manual application only. CareerPilot does not submit applications. Check the employer and final destination on the source website; never pay recruitment fees. A source check is not a guarantee of legitimacy.</p></Card></div><aside className="space-y-6"><Card className="p-6"><h2 className="font-semibold text-ink">Passport match</h2>{match ? <><div className="mt-4 flex items-end justify-between"><span className="text-sm text-muted">Internal heuristic</span><span className="text-3xl font-semibold text-brand">{match.score}</span></div><ul className="mt-5 space-y-2 text-sm leading-6 text-muted">{match.reasons.map((reason) => <li key={reason}>✓ {reason}</li>)}</ul>{match.conflicts.length > 0 && <div className="mt-5 border-t border-line pt-4"><p className="text-sm font-semibold text-ink">Review these conflicts</p><ul className="mt-2 space-y-2 text-sm leading-6 text-amber-900">{match.conflicts.map((conflict) => <li key={conflict}>• {conflict}</li>)}</ul></div>}<p className="mt-5 text-xs leading-5 text-muted">{match.score_method}</p></> : <p className="mt-3 text-sm text-muted">No match data available.</p>}</Card><Card className="p-6"><h2 className="font-semibold text-ink">Skill gap</h2>{gaps && <><p className="mt-2 text-sm text-muted">Stored Passport evidence compared with source-provided skills.</p><SkillList title="Matched" items={gaps.matched_skills} tone="green" /><SkillList title="Missing" items={gaps.missing_skills} tone="amber" /><SkillList title="Uncertain" items={gaps.uncertain_skills} tone="slate" /><p className="mt-4 text-xs leading-5 text-muted">{gaps.normalization_rule}</p></>}</Card></aside></div><SourceHealthNotice /></JobShell>;
}

function JobShell({ children }: { children: React.ReactNode }) { return <main className="min-h-screen bg-slate-50 px-5 py-6 sm:px-8 sm:py-10 lg:px-12"><div className="mx-auto max-w-6xl"><Link className="inline-flex items-center gap-2 text-sm font-medium text-muted hover:text-ink" href="/jobs"><ArrowLeft className="size-4" aria-hidden="true" />All jobs</Link><div className="mt-7">{children}</div></div></main>; }
function Info({ label, value }: { label: string; value: string | null }) { return <div><p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">{label}</p><p className="mt-1 break-words text-sm leading-6 text-ink">{value || "Not provided by source"}</p></div>; }
function SkillList({ title, items, tone }: { title: string; items: string[]; tone: "green" | "amber" | "slate" }) { if (!items.length) return null; const classes = { green: "text-emerald-700", amber: "text-amber-800", slate: "text-slate-600" }; return <div className="mt-5"><p className={`text-xs font-semibold uppercase tracking-[0.14em] ${classes[tone]}`}>{title}</p><p className="mt-2 text-sm leading-6 text-muted">{items.join(", ")}</p></div>; }

export function SavedJobsPage() {
  const [result, setResult] = useState<SavedPage | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => { setLoading(true); setError(null); try { setResult(await apiRequest<SavedPage>(`/saved-jobs?page=${page}&page_size=10`)); } catch (caught) { setError(caught instanceof ApiError ? caught.message : "Could not load saved jobs."); } finally { setLoading(false); } }, [page]);
  useEffect(() => { void load(); }, [load]);
  return <main className="min-h-screen bg-slate-50 px-5 py-6 sm:px-8 sm:py-10 lg:px-12"><div className="mx-auto max-w-6xl"><header className="flex flex-wrap items-end justify-between gap-5 border-b border-line pb-7"><div><Link className="inline-flex items-center gap-2 text-sm font-medium text-muted hover:text-ink" href="/jobs"><ArrowLeft className="size-4" aria-hidden="true" />All jobs</Link><p className="mt-7 text-sm font-semibold uppercase tracking-[0.16em] text-brand">Your shortlist</p><h1 className="mt-2 text-3xl font-semibold tracking-[-0.03em] text-ink">Saved jobs</h1><p className="mt-3 text-muted">Keep opportunities you want to review. Saving never submits an application.</p></div><Button asChild variant="secondary"><Link href="/passport">Career Passport</Link></Button></header>{error && <div className="mt-6"><ErrorNotice error={error} /></div>}{loading ? <Card className="mt-6 p-8 text-sm text-muted">Loading saved jobs…</Card> : result && result.items.length ? <><div className="mt-6 grid gap-4">{result.items.map((item) => <JobCard key={item.job.id} job={item.job} onSaved={() => void load()} />)}</div><Pagination page={result.page} hasNext={result.has_next} onChange={setPage} /></> : <Card className="mt-6 border-dashed p-10 text-center"><Bookmark className="mx-auto size-8 text-muted" aria-hidden="true" /><h2 className="mt-4 text-lg font-semibold text-ink">Nothing saved yet</h2><p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted">Browse authorized job listings and save the ones you want to compare with your Career Passport.</p><Button className="mt-5" asChild><Link href="/jobs">Browse jobs</Link></Button></Card>}</div></main>;
}
