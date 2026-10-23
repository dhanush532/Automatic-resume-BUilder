"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { gsap } from "gsap";
import { useGSAP } from "@gsap/react";
import { ArrowUpRight, Copy, FilePlus2, FileText, Upload, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ApiError, apiRequest } from "@/lib/api";

gsap.registerPlugin(useGSAP);

export type ResumeTemplate = { id: string; name: string; slug: string; description: string; template_key: string; is_active: boolean; display_name?: string | null; layout?: string | null; ats_safe?: boolean; recommended?: boolean };
export type ResumeVersion = { id: string; resume_id: string; version_number: number; source: string; content_snapshot: Record<string, unknown>; template_id: string; created_at: string; restored_from_version_id: string | null; change_summary: string | null };
export type Resume = { id: string; name: string; template_id: string; type: string; status: string; template: ResumeTemplate; latest_version: ResumeVersion | null; version_count: number; updated_at: string };

export function ResumeListPage() {
  const router = useRouter();
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [signedOut, setSignedOut] = useState(false);
  async function load() {
    try { setResumes(await apiRequest<Resume[]>("/resumes")); }
    catch (caught) { if (caught instanceof ApiError && caught.status === 401) setSignedOut(true); else setError(caught instanceof Error ? caught.message : "Could not load your resumes."); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, []);
  async function duplicate(id: string) {
    setBusy(true); setError("");
    try { const copy = await apiRequest<Resume>(`/resumes/${id}/duplicate`, { method: "POST" }); router.push(`/resumes/${copy.id}`); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Could not copy this resume."); }
    finally { setBusy(false); }
  }
  async function remove(resume: Resume) {
    if (!window.confirm(`Delete ${resume.name} and all its versions? This cannot be undone.`)) return;
    setBusy(true); setError("");
    try { await apiRequest(`/resumes/${resume.id}`, { method: "DELETE" }); await load(); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Could not delete this resume."); }
    finally { setBusy(false); }
  }
  return <ResumeShell title="Your next chapter, in drafts." description="Keep your strongest versions together. Start with an existing resume or create one from your career profile.">
    <div className="flex flex-wrap items-center justify-between gap-4"><p className="text-sm text-muted">{resumes.length ? `${resumes.length} saved ${resumes.length === 1 ? "resume" : "resumes"}` : "A little progress starts here."}</p><div className="flex flex-wrap gap-2"><Button asChild variant="secondary"><Link href="/resumes/new"><FilePlus2 size={16} />From my profile</Link></Button><Button asChild><Link href="/review"><Upload size={16} />Import a resume</Link></Button></div></div>
    {error && <Notice>{error}</Notice>}{loading ? <Card className="mt-6 p-8" role="status">Getting your latest drafts…</Card> : signedOut ? <Card className="mt-8 p-8 sm:p-12"><FileText className="text-brand" size={32} /><h2 className="mt-6 text-2xl font-semibold tracking-tight">Your drafts deserve a home.</h2><p className="mt-3 max-w-lg text-sm leading-7 text-muted">Sign in to keep your resumes and version history together. Just want feedback? You can check a resume without an account.</p><div className="mt-6 flex flex-wrap gap-3"><Button asChild><Link href="/login">Sign in to my workspace</Link></Button><Button asChild variant="secondary"><Link href="/review">Check a resume <ArrowUpRight size={16} /></Link></Button></div></Card> : resumes.length ? <div className="mt-7 grid gap-5 md:grid-cols-2">{resumes.map(resume => <Card className="p-6 sm:p-7" key={resume.id}><div className="flex items-start justify-between gap-4"><div><p className="text-xs font-semibold uppercase tracking-wider text-brand">{resume.latest_version?.content_snapshot.source === "document_import" ? "Imported resume" : resume.type === "master" ? "Master resume" : "Tailored resume"}</p><h2 className="mt-3 text-xl font-semibold tracking-tight">{resume.name}</h2><p className="mt-2 text-xs text-muted">{resume.template.display_name ?? resume.template.name} · {resume.version_count} {resume.version_count === 1 ? "version" : "versions"}</p></div><span className="rounded-xl bg-emerald-50 p-3 text-emerald-800"><FileText size={22} strokeWidth={1.5} /></span></div><p className="mt-6 border-t pt-4 text-xs text-muted">Updated {new Date(resume.updated_at).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}</p><div className="mt-5 flex flex-wrap gap-2"><Button asChild><Link href={`/resumes/${resume.id}`}>Open draft <ArrowUpRight size={15} /></Link></Button><Button asChild variant="secondary"><Link href={`/resumes/${resume.id}/preview`}>Preview</Link></Button><Button variant="ghost" disabled={busy} onClick={() => void duplicate(resume.id)} aria-label={`Duplicate ${resume.name}`}><Copy size={16} /></Button><Button variant="ghost" disabled={busy} className="text-rose-700" onClick={() => void remove(resume)} aria-label={`Delete ${resume.name}`}><Trash2 size={16} /></Button></div></Card>)}</div> : <Card className="mt-8 border-dashed p-8 text-center sm:p-14"><FileText size={35} strokeWidth={1.4} className="mx-auto text-emerald-700" /><h2 className="mt-5 text-2xl font-semibold tracking-tight">You’ve already done the hard work.</h2><p className="mx-auto mt-3 max-w-md text-sm leading-7 text-muted">Bring your existing resume. Get feedback, edit the text, and save your first version without retyping your career.</p><Button asChild className="mt-7"><Link href="/review">Start with my resume <ArrowUpRight size={16} /></Link></Button></Card>}
  </ResumeShell>;
}

export function ResumeNewPage() {
  const router = useRouter();
  const [templates, setTemplates] = useState<ResumeTemplate[]>([]); const [name, setName] = useState("My resume"); const [templateId, setTemplateId] = useState(""); const [loading, setLoading] = useState(true); const [saving, setSaving] = useState(false); const [error, setError] = useState("");
  const [role, setRole] = useState(""); const [jobDescription, setJobDescription] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    void apiRequest<ResumeTemplate[]>("/resumes/templates", { signal: controller.signal }).then(items => { setTemplates(items); setTemplateId(items[0]?.id ?? ""); }).catch(caught => { if (!controller.signal.aborted) setError(caught instanceof Error ? caught.message : "Could not load layouts."); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, []);
  useEffect(() => {
    const query = role.trim();
    if (query.length < 2) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      void apiRequest<ResumeTemplate[]>(`/resumes/templates?role=${encodeURIComponent(query)}`, { signal: controller.signal }).then(items => {
        setTemplates(items);
        setTemplateId(current => items.some(item => item.id === current) ? current : (items.find(item => item.recommended)?.id ?? current));
      }).catch(() => undefined);
    }, 400);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [role]);
  const targeted = role.trim().length >= 2 && jobDescription.trim().length >= 20;
  const incompleteTarget = !!(role.trim() || jobDescription.trim()) && !targeted;
  async function create() {
    if (incompleteTarget) { setError("Complete both the target title and job description, or clear both to create a master resume."); return; }
    setSaving(true); setError("");
    try { const resume = await apiRequest<Resume>("/resumes", { method: "POST", body: JSON.stringify({ name, template_id: templateId, type: targeted ? "job_specific" : "master", ...(targeted ? { target_job_title: role.trim(), job_description: jobDescription.trim() } : {}) }) }); router.push(`/resumes/${resume.id}`); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Could not create this resume."); }
    finally { setSaving(false); }
  }
  return <ResumeShell title="A fresh take on your experience." description="Create a resume from the information already in your career profile. Add a target job and we will draft a job-specific version from your own evidence."><div className="rounded-xl border border-emerald-200 bg-emerald-50 p-5 text-sm leading-7 text-emerald-900">Already have a resume? <Link href="/review" className="font-semibold underline">Import it instead</Link> and skip the profile forms. Starting from scratch? <Link href="/passport" className="font-semibold underline">Add your career details</Link> first.</div>{error && <Notice>{error}</Notice>}<Card className="mt-6 p-6 sm:p-8"><label className="block max-w-md text-sm font-medium">Resume name<Input className="mt-2" maxLength={160} value={name} onChange={event => setName(event.target.value)} /></label><fieldset className="mt-7"><legend className="text-sm font-semibold">Choose a theme</legend>{loading ? <p className="mt-4 text-sm text-muted">Loading themes…</p> : <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{templates.map(template => <label className={`cursor-pointer rounded-xl border p-5 ${template.id === templateId ? "border-brand bg-indigo-50/40 ring-1 ring-brand" : "hover:border-slate-400"}`} key={template.id}><span className="flex flex-wrap items-center gap-2"><input className="mr-1 accent-brand" type="radio" name="template" value={template.id} checked={templateId === template.id} onChange={() => setTemplateId(template.id)} /><span className="text-sm font-semibold">{template.display_name ?? template.name}</span>{template.recommended && <span className="rounded-full bg-brand px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white">Recommended</span>}{template.ats_safe && <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-800">ATS-safe</span>}</span><span className="mt-3 block text-xs leading-6 text-muted">{template.description}</span></label>)}</div>}</fieldset>
    <div className="mt-7 rounded-xl border border-line bg-white p-5"><h2 className="text-sm font-semibold">Target a job (optional)</h2><p className="mt-1 text-xs leading-5 text-muted">We create a separate job-specific draft that reorders and tightens only evidence already in your profile. Nothing is invented, and your master resume stays untouched.</p><label className="mt-4 block max-w-md text-sm font-medium">Target job title<Input className="mt-2" maxLength={120} placeholder="e.g. Senior Platform Engineer" value={role} onChange={event => setRole(event.target.value)} /></label><label className="mt-4 block text-sm font-medium">Job description<textarea className="mt-2 min-h-[140px] w-full rounded-lg border p-3 text-sm leading-6" maxLength={30000} placeholder="Paste the role requirements so we can surface matched skills and anything missing from your profile." value={jobDescription} onChange={event => setJobDescription(event.target.value)} /></label>{incompleteTarget && <p className="mt-2 text-xs text-amber-800">Use a title of at least 2 characters and a job description of at least 20 characters.</p>}</div>
    {incompleteTarget && <p className="mt-4 text-sm text-amber-800" role="status">Complete both job fields or clear them to continue. Your target will not be silently discarded.</p>}
    <Button className="mt-7" onClick={() => void create()} disabled={loading || saving || !templateId || !name.trim() || incompleteTarget}>{saving ? "Creating your draft…" : targeted ? "Create job-specific draft" : "Create my resume"}<ArrowUpRight size={16} /></Button></Card></ResumeShell>;
}

export function ResumeShell({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  const root = useRef<HTMLElement>(null);
  useGSAP(() => {
    const media = gsap.matchMedia();
    media.add("(prefers-reduced-motion: no-preference)", () => {
      gsap.from(".resume-workspace-heading > *", { y: 12, opacity: 0, duration: .5, stagger: .06, ease: "power2.out" });
      gsap.from(".resume-workspace-body", { y: 16, opacity: 0, duration: .55, delay: .12, ease: "power2.out" });
    });
    return () => media.revert();
  }, { scope: root, dependencies: [title], revertOnUpdate: true });
  return <main ref={root} className="resume-workspace min-h-[100dvh] px-5 py-8 sm:px-8 sm:py-12 lg:px-12"><div className="mx-auto max-w-7xl"><header className="resume-workspace-heading"><p className="text-[10px] font-semibold uppercase tracking-[.18em] text-emerald-800">CareerPilot / Resume studio</p><h1 className="mt-4 text-3xl font-semibold tracking-[-.05em] text-[#173c32] sm:text-4xl">{title}</h1><p className="mt-4 max-w-2xl text-sm leading-7 text-muted">{description}</p><div className="mt-5 flex flex-wrap gap-2 text-[11px] font-medium text-emerald-900"><span className="rounded-full border bg-white px-3 py-1.5">Your experience, well presented</span><span className="rounded-full border bg-white px-3 py-1.5">A4 · Searchable PDF</span></div></header><div className="resume-workspace-body mt-7">{children}</div></div></main>;
}
function Notice({ children }: { children: ReactNode }) { return <p className="mt-5 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800" role="alert">{children}</p>; }
