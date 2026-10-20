"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { ArrowLeft, Download, Eye, History, Save, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiBaseUrl, ApiError, apiRequest } from "@/lib/api";
import { ResumeShell, type Resume, type ResumeTemplate, type ResumeVersion } from "@/components/resumes/resume-list-page";

type Snapshot = { source?: string; imported_text?: string; profile?: { headline?: string; bio?: string }; resume_meta?: { hidden_sections?: string[] } };

export function ResumeEditorPage({ resumeId }: { resumeId: string }) {
  const router = useRouter();
  const [resume, setResume] = useState<Resume | null>(null);
  const [templates, setTemplates] = useState<ResumeTemplate[]>([]);
  const [name, setName] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [headline, setHeadline] = useState("");
  const [summary, setSummary] = useState("");
  const [text, setText] = useState("");
  const [hidden, setHidden] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const load = useCallback(async () => {
    setError("");
    try {
      const [loaded, available] = await Promise.all([apiRequest<Resume>(`/resumes/${resumeId}`), apiRequest<ResumeTemplate[]>("/resumes/templates")]);
      setResume(loaded); setTemplates(available); setName(loaded.name); setTemplateId(loaded.template_id);
      const snapshot = loaded.latest_version?.content_snapshot as Snapshot | undefined;
      setHeadline(snapshot?.profile?.headline ?? ""); setSummary(snapshot?.profile?.bio ?? ""); setText(snapshot?.imported_text ?? ""); setHidden(snapshot?.resume_meta?.hidden_sections ?? []);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not load this resume."); }
    finally { setLoading(false); }
  }, [resumeId]);
  useEffect(() => { void load(); }, [load]);
  const imported = (resume?.latest_version?.content_snapshot as Snapshot)?.source === "document_import";
  async function save() {
    setSaving(true); setError(""); setNotice("");
    try {
      await apiRequest(`/resumes/${resumeId}/versions`, { method: "POST", body: JSON.stringify({
        ...(imported ? { imported_text: text } : { headline_override: headline, summary_override: summary, hidden_sections: hidden }),
        name, template_id: templateId, change_summary: "Saved from resume editor",
      }) });
      setNotice("Your changes were saved as a new version."); await load();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not save this resume."); }
    finally { setSaving(false); }
  }
  async function remove() {
    if (!window.confirm(`Delete ${resume?.name ?? "this resume"} and its versions?`)) return;
    setSaving(true);
    try { await apiRequest(`/resumes/${resumeId}`, { method: "DELETE" }); router.push("/resumes"); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Could not delete this resume."); setSaving(false); }
  }
  if (loading) return <ResumeShell title="Opening your resume…" description="Getting your latest draft."><Card className="p-8" role="status">Loading resume…</Card></ResumeShell>;
  if (!resume) return <ResumeShell title="Let’s get you back on track." description="This resume could not be opened."><Notice>{error}</Notice><Link className="mt-5 inline-block text-brand underline" href="/login">Sign in</Link><Link className="ml-5 text-brand underline" href="/resumes">My resumes</Link></ResumeShell>;
  return <ResumeShell title={resume.name} description={imported ? "Your imported resume, ready for the next draft. Edit the text and keep every version." : "Fine-tune your resume without changing the facts in your career profile."}>
    <div className="flex flex-wrap items-center justify-between gap-3"><Link className="inline-flex items-center gap-2 text-sm text-muted" href="/resumes"><ArrowLeft size={16} />My resumes</Link><div className="flex flex-wrap gap-2"><Button asChild variant="secondary"><Link href={`/resumes/${resumeId}/preview`}><Eye size={16} />Preview</Link></Button><Button asChild variant="secondary"><Link href={`/resumes/${resumeId}/versions`}><History size={16} />History</Link></Button><Button asChild variant="secondary"><a href={`${apiBaseUrl}/resumes/${resumeId}/pdf`}><Download size={16} />Download PDF</a></Button></div></div>
    {error && <Notice>{error}</Notice>}{notice && <p className="mt-5 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800" role="status">{notice}</p>}
    <div className="mt-6 grid items-start gap-6 lg:grid-cols-[1.3fr_.7fr]"><Card className="p-6 sm:p-8"><h2 className="text-lg font-semibold">Make your experience count.</h2><p className="mt-2 text-sm text-muted">Version {resume.latest_version?.version_number ?? 1} · {resume.template.name}</p><label className="mt-6 block text-sm font-medium">Resume name<Input className="mt-2" maxLength={160} value={name} onChange={event => setName(event.target.value)} /></label><label className="mt-5 block text-sm font-medium">Layout<select className="mt-2 h-11 w-full rounded-lg border bg-white px-3 text-sm" value={templateId} onChange={event => setTemplateId(event.target.value)}>{templates.map(template => <option value={template.id} key={template.id}>{template.name}</option>)}</select></label>
    {imported ? <label className="mt-5 block text-sm font-medium">Resume text<textarea className="mt-2 min-h-[480px] w-full rounded-lg border p-4 text-sm leading-7" value={text} maxLength={60000} onChange={event => setText(event.target.value)} /><span className="mt-2 block text-xs text-muted">Imported text is preserved in reading order. Layouts change typography, not your original document’s formatting.</span></label> : <><label className="mt-5 block text-sm font-medium">Headline<Input className="mt-2" maxLength={160} value={headline} onChange={event => setHeadline(event.target.value)} /></label><label className="mt-5 block text-sm font-medium">Summary<textarea className="mt-2 min-h-40 w-full rounded-lg border p-3 text-sm leading-7" maxLength={5000} value={summary} onChange={event => setSummary(event.target.value)} /></label><fieldset className="mt-6"><legend className="text-sm font-medium">Sections to include</legend><div className="mt-3 grid grid-cols-2 gap-3">{["experience", "projects", "education", "skills", "certifications", "courses", "achievements", "languages", "open_source_contributions"].map(section => <label className="flex items-start gap-2 text-xs capitalize" key={section}><input type="checkbox" className="mt-0.5" checked={!hidden.includes(section)} onChange={event => setHidden(current => event.target.checked ? current.filter(key => key !== section) : [...current, section])} />{section.replaceAll("_", " ")}</label>)}</div></fieldset></>}
    <div className="mt-7 flex flex-wrap gap-3"><Button onClick={() => void save()} disabled={saving || !name.trim() || (imported && text.trim().length < 80)}><Save size={16} />{saving ? "Saving…" : "Save a new version"}</Button><Button variant="ghost" className="text-rose-700" disabled={saving} onClick={() => void remove()}><Trash2 size={16} />Delete resume</Button></div></Card>
    <Card className="p-6"><p className="text-xs font-semibold uppercase tracking-wider text-brand">A little clarity</p><h2 className="mt-3 text-xl font-semibold tracking-tight">Show the impact.<br />Keep it true.</h2><ul className="mt-5 space-y-4 text-sm leading-7 text-muted"><li>Lead with what you did, not just what the role involved.</li><li>Add scale or outcomes when you can back them up.</li><li>Keep the strongest, most relevant examples near the top.</li><li>Don’t add skills or accomplishments just to match a job description.</li></ul><Button asChild variant="secondary" className="mt-6"><Link href="/review">Check another resume</Link></Button>{!imported && <p className="mt-5 text-xs leading-6 text-muted">Need to update roles or education? <Link href="/passport" className="text-brand underline">Edit your career profile</Link>.</p>}</Card></div>
  </ResumeShell>;
}

export function ResumeVersionsPage({ resumeId }: { resumeId: string }) {
  const [versions, setVersions] = useState<ResumeVersion[]>([]);
  const [error, setError] = useState(""); const [notice, setNotice] = useState(""); const [busy, setBusy] = useState(false); const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    try { setVersions(await apiRequest<ResumeVersion[]>(`/resumes/${resumeId}/versions`)); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Could not load history."); }
    finally { setLoading(false); }
  }, [resumeId]);
  useEffect(() => { void load(); }, [load]);
  async function restore(id: string) {
    if (!window.confirm("Restore this version? Your history will be kept.")) return;
    setBusy(true); setError("");
    try { await apiRequest(`/resumes/${resumeId}/versions/${id}/restore`, { method: "POST" }); setNotice("Restored as a new version."); await load(); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Could not restore this version."); }
    finally { setBusy(false); }
  }
  return <ResumeShell title="Every draft. Every step forward." description="Restore an earlier version without losing your history."><Link className="text-sm text-brand underline" href={`/resumes/${resumeId}`}>← Back to editor</Link>{error && <Notice>{error}</Notice>}{notice && <p className="mt-4 text-sm text-emerald-700" role="status">{notice}</p>}<div className="mt-6 space-y-3">{loading && <Card className="p-6">Loading history…</Card>}{versions.map(version => <Card className="flex flex-wrap items-center justify-between gap-4 p-5" key={version.id}><div><h2 className="font-semibold">Version {version.version_number}</h2><p className="mt-2 text-xs text-muted">{version.change_summary} · {formatDate(version.created_at)}</p></div><div className="flex gap-2"><Button asChild variant="secondary"><Link href={`/resumes/${resumeId}/preview?version=${version.id}`}>Preview</Link></Button><Button variant="ghost" disabled={busy} onClick={() => void restore(version.id)}>Restore</Button></div></Card>)}</div></ResumeShell>;
}

export function ResumePreviewPage({ resumeId }: { resumeId: string }) {
  const params = useSearchParams(); const version = params.get("version");
  const [preview, setPreview] = useState<{ html: string } | null>(null); const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController(); setPreview(null); setError("");
    void apiRequest<{ html: string }>(`/resumes/${resumeId}/preview${version ? `?version_id=${encodeURIComponent(version)}` : ""}`, { signal: controller.signal }).then(setPreview).catch(caught => { if (!controller.signal.aborted) setError(caught instanceof ApiError ? caught.message : "Could not load preview."); });
    return () => controller.abort();
  }, [resumeId, version]);
  return <ResumeShell title="Ready for a closer look." description="Review the saved content before you send it."><div className="flex flex-wrap justify-between gap-3"><Link className="text-sm text-brand underline" href={`/resumes/${resumeId}`}>← Back to editor</Link><Button asChild variant="secondary"><a href={`${apiBaseUrl}/resumes/${resumeId}/pdf${version ? `?version_id=${encodeURIComponent(version)}` : ""}`}><Download size={16} />Download this version</a></Button></div>{error && <Notice>{error}</Notice>}{!preview && !error && <Card className="mt-6 p-8">Loading preview…</Card>}{preview && <iframe title="Saved resume preview" sandbox="" srcDoc={preview.html} className="mt-6 h-[1000px] w-full rounded-xl border bg-white" />}</ResumeShell>;
}

function formatDate(value: string) { return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)); }
function Notice({ children }: { children: ReactNode }) { return <p className="mt-5 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800" role="alert">{children}</p>; }
