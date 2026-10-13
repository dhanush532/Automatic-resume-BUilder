"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { ArrowLeft, Copy, FilePlus2, FileText, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ApiError, apiRequest } from "@/lib/api";

export type ResumeTemplate = { id: string; name: string; slug: string; description: string; template_key: string; is_active: boolean };
export type ResumeVersion = { id: string; resume_id: string; version_number: number; source: string; content_snapshot: Record<string, unknown>; template_id: string; created_at: string; restored_from_version_id: string | null; change_summary: string | null };
export type Resume = { id: string; name: string; template_id: string; type: string; status: string; template: ResumeTemplate; latest_version: ResumeVersion | null; version_count: number; updated_at: string };

export function ResumeListPage() {
  const router = useRouter();
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true); setError(null);
    try { setResumes(await apiRequest<Resume[]>("/resumes")); } catch (caught) { setError(caught instanceof ApiError ? caught.message : "Could not load resumes."); } finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, []);

  async function duplicate(id: string) { try { const copy = await apiRequest<Resume>(`/resumes/${id}/duplicate`, { method: "POST" }); router.push(`/resumes/${copy.id}`); } catch (caught) { setError(caught instanceof ApiError ? caught.message : "Could not duplicate resume."); } }
  async function remove(resume: Resume) { if (!window.confirm(`Delete ${resume.name}? All versions will be removed and this cannot be undone.`)) return; try { await apiRequest(`/resumes/${resume.id}`, { method: "DELETE" }); await load(); } catch (caught) { setError(caught instanceof ApiError ? caught.message : "Could not delete resume."); } }

  return <ResumeShell title="Resumes" description="Your first master resume is created automatically from saved Career Passport details. You can also create additional tailored resumes whenever you need them."><div className="flex flex-wrap items-center justify-between gap-4"><Link className="inline-flex items-center gap-2 text-sm font-medium text-muted hover:text-ink" href="/"><ArrowLeft className="size-4" aria-hidden="true" />Home</Link><Button asChild><Link href="/resumes/new"><FilePlus2 className="size-4" aria-hidden="true" />Create resume</Link></Button></div>{error && <Notice>{error}</Notice>}{loading ? <Loading /> : resumes.length ? <div className="mt-6 grid gap-4 md:grid-cols-2">{resumes.map((resume) => <Card className="p-6" key={resume.id}><div className="flex items-start justify-between gap-4"><div><p className="text-xs font-semibold uppercase tracking-[0.14em] text-brand">{resume.type === "master" ? "Master resume" : "Job-specific resume"}</p><h2 className="mt-2 text-xl font-semibold text-ink">{resume.name}</h2><p className="mt-1 text-sm text-muted">{resume.template.name} · {resume.version_count} {resume.version_count === 1 ? "version" : "versions"}</p></div><FileText className="size-5 text-brand" aria-hidden="true" /></div><p className="mt-5 rounded-lg bg-slate-50 px-3 py-3 text-sm text-muted">Every version is a snapshot. Editing this resume never overwrites your Career Passport.</p><div className="mt-5 flex flex-wrap gap-2"><Button asChild><Link href={`/resumes/${resume.id}`}>Open editor</Link></Button><Button asChild variant="secondary"><Link href={`/resumes/${resume.id}/preview`}>Preview</Link></Button><Button variant="ghost" onClick={() => void duplicate(resume.id)}><Copy className="size-4" aria-hidden="true" />Duplicate</Button><Button variant="ghost" className="text-rose-700 hover:bg-rose-50" onClick={() => void remove(resume)}><Trash2 className="size-4" aria-hidden="true" />Delete</Button></div></Card>)}</div> : <Card className="mt-6 border-dashed p-10 text-center"><FileText className="mx-auto size-8 text-muted" aria-hidden="true" /><h2 className="mt-4 text-lg font-semibold text-ink">No resumes yet</h2><p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted">Save your first Career Passport detail and a draft master resume will be created automatically. You can still choose a template and create another resume manually.</p><Button className="mt-5" asChild><Link href="/resumes/new">Create your first resume</Link></Button></Card>}</ResumeShell>;
}

export function ResumeNewPage() {
  const router = useRouter();
  const [templates, setTemplates] = useState<ResumeTemplate[]>([]); const [name, setName] = useState("My resume"); const [templateId, setTemplateId] = useState(""); const [type, setType] = useState("master"); const [loading, setLoading] = useState(true); const [saving, setSaving] = useState(false); const [error, setError] = useState<string | null>(null);
  useEffect(() => { void apiRequest<ResumeTemplate[]>("/resumes/templates").then((items) => { setTemplates(items); setTemplateId(items[0]?.id ?? ""); }).catch((caught) => setError(caught instanceof ApiError ? caught.message : "Could not load templates.")).finally(() => setLoading(false)); }, []);
  async function create() { setSaving(true); setError(null); try { const resume = await apiRequest<Resume>("/resumes", { method: "POST", body: JSON.stringify({ name, template_id: templateId, type }) }); router.push(`/resumes/${resume.id}`); } catch (caught) { setError(caught instanceof ApiError ? caught.message : "Could not create resume."); } finally { setSaving(false); } }
  return <ResumeShell title="Create a resume" description="Choose a deterministic layout. Your first version will be derived from the current Career Passport snapshot."><Link className="inline-flex items-center gap-2 text-sm font-medium text-muted hover:text-ink" href="/resumes"><ArrowLeft className="size-4" aria-hidden="true" />Back to resumes</Link>{error && <Notice>{error}</Notice>}<Card className="mt-6 p-6 sm:p-8"><div className="grid gap-6 md:grid-cols-[.7fr_1.3fr]"><div><label className="block text-sm font-medium text-ink">Resume name<Input className="mt-2" value={name} onChange={(event) => setName(event.target.value)} /></label><label className="mt-5 block text-sm font-medium text-ink">Resume type<select className="mt-2 h-11 w-full rounded-lg border border-line bg-white px-3 text-sm text-ink" value={type} onChange={(event) => setType(event.target.value)}><option value="master">Master resume</option><option value="job_specific">Job-specific resume</option></select></label><Button className="mt-6" onClick={() => void create()} disabled={loading || saving || !templateId}>{saving ? "Creating…" : "Create resume"}</Button></div><div><p className="text-sm font-semibold text-ink">Select a template</p><div className="mt-3 grid gap-3 sm:grid-cols-2">{templates.map((template) => <button type="button" className={`rounded-xl border p-4 text-left transition ${template.id === templateId ? "border-brand bg-indigo-50/50 ring-2 ring-indigo-100" : "border-line hover:border-brand"}`} key={template.id} onClick={() => setTemplateId(template.id)}><span className="font-semibold text-ink">{template.name}</span><span className="mt-1 block text-sm leading-5 text-muted">{template.description}</span></button>)}</div>{!templates.length && !loading && <p className="mt-4 text-sm text-muted">No active templates are available.</p>}</div></div></Card></ResumeShell>;
}

export function ResumeShell({ title, description, children }: { title: string; description: string; children: ReactNode }) { return <main className="min-h-screen bg-slate-50 px-5 py-6 sm:px-8 sm:py-10 lg:px-12"><div className="mx-auto max-w-6xl"><header className="border-b border-line pb-7"><p className="text-sm font-semibold uppercase tracking-[0.16em] text-brand">Resume system</p><h1 className="mt-2 text-3xl font-semibold tracking-[-0.03em] text-ink">{title}</h1><p className="mt-3 max-w-2xl leading-7 text-muted">{description}</p></header><div className="mt-7">{children}</div></div></main>; }
function Loading() { return <Card className="mt-6 p-8"><div className="h-5 w-40 animate-pulse rounded bg-slate-100" /><div className="mt-4 h-3 w-3/4 animate-pulse rounded bg-slate-100" /></Card>; }
function Notice({ children }: { children: ReactNode }) { return <p className="mt-5 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800" role="alert">{children}</p>; }
