"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { ArrowLeft, Download, Eye, History, Save, Trash2, Wand2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiBaseUrl, ApiError, apiRequest } from "@/lib/api";
import { ResumeShell, type Resume, type ResumeTemplate, type ResumeVersion } from "@/components/resumes/resume-list-page";

type Design = { accent?: string | null; font: "theme" | "sans" | "serif" | "mono"; spacing: "compact" | "comfortable"; margin_mm: number };
type JobTargetAnalysis = { skills?: string[]; matched_keywords?: string[]; missing_qualifications?: string[]; qualification_note?: string; required_qualifications?: string[]; preferred_qualifications?: string[] };
type JobTarget = { title: string; description: string; method: string; note: string; recommended_template_key?: string; analysis?: JobTargetAnalysis };
type Snapshot = { source?: string; imported_text?: string; profile?: { headline?: string | null; bio?: string | null }; resume_meta?: { hidden_sections?: string[]; design?: Design }; job_target?: JobTarget };

const DEFAULT_DESIGN: Design = { accent: null, font: "theme", spacing: "comfortable", margin_mm: 17 };

// Preview and download share the same immutable PDF bytes, including unsaved edits.
function usePdfUrl(base64: string) {
  const [document, setDocument] = useState({ base64: "", url: "" });
  useEffect(() => {
    if (!base64) { setDocument({ base64: "", url: "" }); return; }
    const bytes = Uint8Array.from(atob(base64), character => character.charCodeAt(0));
    const next = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
    setDocument({ base64, url: next });
    return () => URL.revokeObjectURL(next);
  }, [base64]);
  return document.base64 === base64 ? document.url : "";
}

function PdfThumbnail({ pdf, name }: { pdf: string; name: string }) {
  const url = usePdfUrl(pdf);
  return url ? <iframe loading="lazy" title={`${name} document thumbnail`} aria-hidden tabIndex={-1} src={`${url}#toolbar=0&navpanes=0&view=FitH`} className="pointer-events-none absolute left-0 top-0 h-[1000px] w-[700px] origin-top-left scale-[0.27]" /> : null;
}

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
  const [design, setDesign] = useState<Design>(DEFAULT_DESIGN);
  const [atsSafe, setAtsSafe] = useState(false);
  const [previewPdf, setPreviewPdf] = useState("");
  const [previewKey, setPreviewKey] = useState("");
  const [previewError, setPreviewError] = useState("");
  const [previewAttempt, setPreviewAttempt] = useState(0);
  const previewUrl = usePdfUrl(previewPdf);
  const [thumbs, setThumbs] = useState<Record<string, string>>({});
  const [jobTitle, setJobTitle] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const snapshot = resume?.latest_version?.content_snapshot as Snapshot | undefined;
  const imported = snapshot?.source === "document_import";
  const jobTarget = snapshot?.job_target;
  const load = useCallback(async () => {
    setError("");
    try {
      const [loaded, available] = await Promise.all([apiRequest<Resume>(`/resumes/${resumeId}`), apiRequest<ResumeTemplate[]>("/resumes/templates")]);
      setResume(loaded); setTemplates(available); setName(loaded.name); setTemplateId(loaded.template_id);
      const content = loaded.latest_version?.content_snapshot as Snapshot | undefined;
      setHeadline(content?.profile?.headline ?? ""); setSummary(content?.profile?.bio ?? ""); setText(content?.imported_text ?? ""); setHidden(content?.resume_meta?.hidden_sections ?? []);
      setDesign(content?.resume_meta?.design ?? DEFAULT_DESIGN);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not load this resume."); }
    finally { setLoading(false); }
  }, [resumeId]);
  useEffect(() => { void load(); }, [load]);

  const edits = useMemo(() => (imported
    ? { ...(text.trim().length >= 80 ? { imported_text: text } : {}), design }
    : { headline_override: headline, summary_override: summary, hidden_sections: hidden, design }), [imported, text, design, headline, summary, hidden]);
  const draftKey = JSON.stringify({ templateId, edits, atsSafe, resumeId, version: resume?.latest_version?.id });
  const currentPdfUrl = previewKey === draftKey && !previewError && (!imported || text.trim().length >= 80) ? previewUrl : "";

  useEffect(() => {
    if (!resume || !templateId) return;
    if (imported && text.trim().length < 80) { setPreviewError("Add at least 80 characters of resume text to render this draft."); return; }
    const controller = new AbortController();
    const timer = setTimeout(() => {
      setPreviewError("");
      void apiRequest<{ pdf_base64: string }>("/resumes/preview", { method: "POST", body: JSON.stringify({ template_id: templateId, base_resume_id: resumeId, edits, ats_safe: atsSafe, include_pdf: true }), signal: controller.signal })
        .then(result => { if (!controller.signal.aborted) { setPreviewPdf(result.pdf_base64); setPreviewKey(draftKey); } })
        .catch(caught => { if (!controller.signal.aborted) setPreviewError(caught instanceof Error ? caught.message : "Could not render the document. Try again."); });
    }, 400);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [resume, resumeId, templateId, edits, atsSafe, draftKey, previewAttempt, imported, text]);

  useEffect(() => {
    if (!resume || !templates.length) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      void Promise.all(templates.map(template => apiRequest<{ pdf_base64: string }>("/resumes/preview", { method: "POST", body: JSON.stringify({ template_id: template.id, base_resume_id: resumeId, edits, include_pdf: true }), signal: controller.signal })
        .then(result => [template.id, result.pdf_base64] as const).catch(() => [template.id, ""] as const)))
        .then(pairs => { if (!controller.signal.aborted) setThumbs(Object.fromEntries(pairs)); });
    }, 1200);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [resume, templates, resumeId, edits, previewAttempt]);

  async function save() {
    setSaving(true); setError(""); setNotice("");
    try {
      await apiRequest(`/resumes/${resumeId}/versions`, { method: "POST", body: JSON.stringify({
        ...(imported ? { imported_text: text } : { headline_override: headline, summary_override: summary, hidden_sections: hidden }),
        design, name, template_id: templateId, change_summary: "Saved from resume editor",
      }) });
      setNotice("Your changes were saved as a new version."); await load();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not save this resume."); }
    finally { setSaving(false); }
  }

  async function createTargeted() {
    setSaving(true); setError(""); setNotice("");
    try {
      const created = await apiRequest<Resume>("/resumes", { method: "POST", body: JSON.stringify({
        name: `${name} — ${jobTitle}`.slice(0, 160), template_id: templateId, type: "job_specific",
        base_resume_id: resumeId, target_job_title: jobTitle.trim(), job_description: jobDescription.trim(), design,
      }) });
      router.push(`/resumes/${created.id}`);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not create a job-specific draft."); setSaving(false); }
  }

  async function remove() {
    if (!window.confirm(`Delete ${resume?.name ?? "this resume"} and its versions?`)) return;
    setSaving(true);
    try { await apiRequest(`/resumes/${resumeId}`, { method: "DELETE" }); router.push("/resumes"); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Could not delete this resume."); setSaving(false); }
  }

  const activeTheme = templates.find(template => template.id === templateId);

  if (loading) return <ResumeShell title="Opening your resume…" description="Getting your latest draft."><Card className="p-8" role="status">Loading resume…</Card></ResumeShell>;
  if (!resume) return <ResumeShell title="Let’s get you back on track." description="This resume could not be opened."><Notice>{error}</Notice><Link className="mt-5 inline-block text-brand underline" href="/login">Sign in</Link><Link className="ml-5 text-brand underline" href="/resumes">My resumes</Link></ResumeShell>;
  return <ResumeShell title={resume.name} description={imported ? "Your imported resume, ready for the next draft. Pick a theme, fine-tune the text and keep every version." : "Choose a theme, fine-tune your resume and keep every version — without changing the facts in your career profile."}>
    <div className="flex flex-wrap items-center justify-between gap-3"><Link className="inline-flex items-center gap-2 text-sm text-muted" href="/resumes"><ArrowLeft size={16} />My resumes</Link><div className="flex flex-wrap gap-2"><Button asChild variant="secondary"><Link href={`/resumes/${resumeId}/preview`}><Eye size={16} />Saved preview</Link></Button><Button asChild variant="secondary"><Link href={`/resumes/${resumeId}/versions`}><History size={16} />History</Link></Button><Button asChild variant="secondary"><a role="link" tabIndex={currentPdfUrl ? 0 : -1} href={currentPdfUrl || undefined} aria-disabled={!currentPdfUrl} onClick={event => { if (!currentPdfUrl) event.preventDefault(); }} download="resume.pdf"><Download size={16} />Download PDF</a></Button></div></div>
    {error && <Notice>{error}</Notice>}{notice && <p className="mt-5 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800" role="status">{notice}</p>}
    <div className="mt-6 grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <div>
        <Card className="p-6 sm:p-8">
          <h2 className="text-lg font-semibold">Make your experience count.</h2>
          <p className="mt-2 text-sm text-muted">Version {resume.latest_version?.version_number ?? 1} · {activeTheme?.display_name ?? resume.template.name}</p>
          <label className="mt-6 block text-sm font-medium">Resume name<Input className="mt-2" maxLength={160} value={name} onChange={event => setName(event.target.value)} /></label>

          <fieldset className="mt-7">
            <legend className="text-sm font-semibold">Theme</legend>
            <p className="mt-1 text-xs leading-5 text-muted">Six distinct layouts, each rendered from your actual content. Thumbnails update as you edit.</p>
            <div className="mt-3 grid grid-cols-2 gap-3">
              {templates.map(template => (
                <label className={`cursor-pointer rounded-xl border p-3 ${template.id === templateId ? "border-brand ring-1 ring-brand" : "hover:border-slate-400"}`} key={template.id}>
                  <span className="flex flex-wrap items-center gap-2">
                    <input className="accent-brand" type="radio" name="theme" value={template.id} checked={templateId === template.id} onChange={() => setTemplateId(template.id)} />
                    <span className="text-sm font-semibold">{template.display_name ?? template.name}</span>
                    {template.ats_safe && <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-800">ATS</span>}
                  </span>
                  <span className="relative mt-2 block h-[150px] w-full overflow-hidden rounded-lg border bg-white">
                    {thumbs[template.id] ? <PdfThumbnail pdf={thumbs[template.id]} name={template.display_name ?? template.name} /> : <span className="flex h-full items-center justify-center text-[11px] text-muted" role="status">{thumbs[template.id] === "" ? "Preview unavailable — retry below" : "Rendering…"}</span>}
                  </span>
                  <span className="mt-2 block text-[11px] leading-5 text-muted">{template.description}</span>
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset className="mt-7">
            <legend className="text-sm font-semibold">Customize</legend>
            <div className="mt-3 grid gap-4 sm:grid-cols-2">
              <label className="text-xs font-medium">Accent color
                <span className="mt-2 flex items-center gap-2">
                  <input aria-label="Accent color" type="color" className="h-9 w-12 cursor-pointer rounded border bg-white" value={design.accent ?? "#173c32"} onChange={event => setDesign(current => ({ ...current, accent: event.target.value }))} />
                  <Button variant="ghost" disabled={!design.accent} onClick={() => setDesign(current => ({ ...current, accent: null }))}>Use theme color</Button>
                </span>
              </label>
              <label className="text-xs font-medium">Typeface
                <select className="mt-2 h-10 w-full rounded-lg border bg-white px-3 text-sm" value={design.font} onChange={event => setDesign(current => ({ ...current, font: event.target.value as Design["font"] }))}>
                  <option value="theme">Theme default</option><option value="sans">Sans-serif</option><option value="serif">Serif</option><option value="mono">Monospace</option>
                </select>
              </label>
              <label className="text-xs font-medium">Spacing
                <select className="mt-2 h-10 w-full rounded-lg border bg-white px-3 text-sm" value={design.spacing} onChange={event => setDesign(current => ({ ...current, spacing: event.target.value as Design["spacing"] }))}>
                  <option value="comfortable">Comfortable</option><option value="compact">Compact</option>
                </select>
              </label>
              <label className="text-xs font-medium">Margins — {design.margin_mm} mm
                <input aria-label="Margins in millimetres" type="range" min={12} max={25} className="mt-3 w-full accent-brand" value={design.margin_mm} onChange={event => setDesign(current => ({ ...current, margin_mm: Number(event.target.value) }))} />
              </label>
            </div>
            <label className="mt-5 flex items-start gap-2 text-sm">
              <input type="checkbox" className="mt-1 accent-brand" checked={atsSafe} onChange={event => setAtsSafe(event.target.checked)} />
              <span>ATS-safe preview and PDF <span className="block text-xs leading-5 text-muted">Exports with the plain Technical ATS layout, whatever theme is selected.</span></span>
            </label>
          </fieldset>

          {imported ? <label className="mt-7 block text-sm font-medium">Resume text<textarea className="mt-2 min-h-[320px] w-full rounded-lg border p-4 text-sm leading-7" value={text} maxLength={60000} onChange={event => setText(event.target.value)} /><span className="mt-2 block text-xs text-muted">Imported text is preserved in reading order. Themes change typography, not your original document’s formatting.</span></label> : <><label className="mt-7 block text-sm font-medium">Headline<Input className="mt-2" maxLength={160} value={headline} onChange={event => setHeadline(event.target.value)} /></label><label className="mt-5 block text-sm font-medium">Summary<textarea className="mt-2 min-h-40 w-full rounded-lg border p-3 text-sm leading-7" maxLength={5000} value={summary} onChange={event => setSummary(event.target.value)} /></label><fieldset className="mt-6"><legend className="text-sm font-medium">Sections to include</legend><div className="mt-3 grid grid-cols-2 gap-3">{["experience", "projects", "education", "skills", "certifications", "courses", "achievements", "languages", "open_source_contributions"].map(section => <label className="flex items-start gap-2 text-xs capitalize" key={section}><input type="checkbox" className="mt-0.5" checked={!hidden.includes(section)} onChange={event => setHidden(current => event.target.checked ? current.filter(key => key !== section) : [...current, section])} />{section.replaceAll("_", " ")}</label>)}</div></fieldset></>}

          <div className="mt-7 flex flex-wrap gap-3"><Button onClick={() => void save()} disabled={saving || !name.trim() || (imported && text.trim().length < 80)}><Save size={16} />{saving ? "Saving…" : "Save a new version"}</Button><Button variant="ghost" className="text-rose-700" disabled={saving} onClick={() => void remove()}><Trash2 size={16} />Delete resume</Button></div>
        </Card>

        {jobTarget && <Card className="mt-6 p-6">
          <p className="text-xs font-semibold uppercase tracking-wider text-brand">Job-targeted draft</p>
          <h2 className="mt-3 text-xl font-semibold tracking-tight">{jobTarget.title}</h2>
          <p className="mt-2 text-sm leading-6 text-muted">{jobTarget.note}</p>
          {(jobTarget.analysis?.required_qualifications?.length || jobTarget.analysis?.preferred_qualifications?.length) ? <div className="mt-4 grid gap-4 sm:grid-cols-2">{(["required_qualifications", "preferred_qualifications"] as const).map(key => <div key={key}><h3 className="text-xs font-semibold">{key === "required_qualifications" ? "Required in the posting" : "Preferred in the posting"}</h3><ul className="mt-2 list-disc space-y-1 pl-4 text-xs leading-5 text-muted">{jobTarget.analysis?.[key]?.slice(0, 6).map(item => <li key={item}>{item}</li>)}</ul></div>)}</div> : null}
          {jobTarget.analysis?.missing_qualifications?.length ? <div className="mt-4"><h3 className="text-sm font-semibold">Needs your review — not evidenced in your profile</h3><ul className="mt-2 space-y-1 text-sm leading-6 text-muted">{jobTarget.analysis.missing_qualifications.map(item => <li key={item}>{item}</li>)}</ul>{jobTarget.analysis.qualification_note && <p className="mt-2 text-xs leading-5 text-muted">{jobTarget.analysis.qualification_note}</p>}</div> : null}
          {jobTarget.analysis?.matched_keywords?.length ? <p className="mt-4 text-xs leading-5 text-muted">Matched terms: {jobTarget.analysis.matched_keywords.slice(0, 12).join(", ")}</p> : null}
        </Card>}

        <Card className="mt-6 p-6">
          <h2 className="text-lg font-semibold">Tailor for a job</h2>
          <p className="mt-2 text-sm leading-6 text-muted">Creates a new job-specific resume from this one. It reorders and tightens only your own evidence, reports anything the job asks for that you have not listed, and never invents experience, skills or credentials.</p>
          <label className="mt-4 block text-sm font-medium">Target job title<Input className="mt-2" maxLength={120} placeholder="e.g. Senior Platform Engineer" value={jobTitle} onChange={event => setJobTitle(event.target.value)} /></label>
          <label className="mt-4 block text-sm font-medium">Job description<textarea className="mt-2 min-h-[160px] w-full rounded-lg border p-3 text-sm leading-6" maxLength={30000} placeholder="Paste the requirements from the role." value={jobDescription} onChange={event => setJobDescription(event.target.value)} /></label>
          <Button className="mt-4" onClick={() => void createTargeted()} disabled={saving || jobTitle.trim().length < 2 || jobDescription.trim().length < 20}><Wand2 size={16} />{saving ? "Creating…" : "Create job-specific draft"}</Button>
        </Card>

        <Card className="mt-6 p-6"><p className="text-xs font-semibold uppercase tracking-wider text-brand">A little clarity</p><h2 className="mt-3 text-xl font-semibold tracking-tight">Show the impact.<br />Keep it true.</h2><ul className="mt-5 space-y-4 text-sm leading-7 text-muted"><li>Lead with what you did, not just what the role involved.</li><li>Add scale or outcomes when you can back them up.</li><li>Keep the strongest, most relevant examples near the top.</li><li>Don’t add skills or accomplishments just to match a job description.</li></ul><Button asChild variant="secondary" className="mt-6"><Link href="/review">Check another resume</Link></Button>{!imported && <p className="mt-5 text-xs leading-6 text-muted">Need to update roles or education? <Link href="/passport" className="text-brand underline">Edit your career profile</Link>.</p>}</Card>
      </div>

      <Card className="p-6 lg:sticky lg:top-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div><h2 className="text-lg font-semibold">Live document preview</h2><p className="mt-1 text-xs text-muted">The actual A4 PDF, including unsaved edits. Download uses these same document bytes.</p></div>
          <Button asChild variant="secondary"><a role="link" tabIndex={currentPdfUrl ? 0 : -1} href={currentPdfUrl || undefined} aria-disabled={!currentPdfUrl} onClick={event => { if (!currentPdfUrl) event.preventDefault(); }} download="resume.pdf"><Download size={16} />PDF</a></Button>
        </div>
        {previewError && <Notice>{previewError}</Notice>}
        <Button variant="ghost" className="mt-3" onClick={() => setPreviewAttempt(attempt => attempt + 1)}>Retry document previews</Button>
        {previewUrl && !currentPdfUrl && !previewError && <p className="mt-3 text-xs text-muted" role="status">Updating the document… Download is available when the current draft is ready.</p>}
        {previewUrl ? <><iframe title="Live resume preview" src={`${previewUrl}#toolbar=0&navpanes=0&view=FitH`} className="mt-4 h-[860px] w-full rounded-xl border bg-white" /><a href={previewUrl} target="_blank" rel="noreferrer" className="mt-3 inline-block text-xs text-brand underline">Open the actual PDF in a new tab</a></> : <div className="mt-4 flex h-[320px] items-center justify-center rounded-xl border bg-white text-sm text-muted" role="status">Rendering preview…</div>}
      </Card>
    </div>
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
  const [preview, setPreview] = useState<{ pdf_base64: string } | null>(null); const [error, setError] = useState("");
  const pdfUrl = usePdfUrl(preview?.pdf_base64 ?? "");
  useEffect(() => {
    const controller = new AbortController(); setPreview(null); setError("");
    void apiRequest<{ pdf_base64: string }>(`/resumes/${resumeId}/preview?include_pdf=true${version ? `&version_id=${encodeURIComponent(version)}` : ""}`, { signal: controller.signal }).then(setPreview).catch(caught => { if (!controller.signal.aborted) setError(caught instanceof ApiError ? caught.message : "Could not load preview."); });
    return () => controller.abort();
  }, [resumeId, version]);
  return <ResumeShell title="Ready for a closer look." description="Review the actual saved PDF before you send it."><div className="flex flex-wrap justify-between gap-3"><Link className="text-sm text-brand underline" href={`/resumes/${resumeId}`}>← Back to editor</Link><Button asChild variant="secondary"><a href={`${apiBaseUrl}/resumes/${resumeId}/pdf${version ? `?version_id=${encodeURIComponent(version)}` : ""}`}><Download size={16} />Download this version</a></Button></div>{error && <Notice>{error}</Notice>}{!preview && !error && <Card className="mt-6 p-8">Loading preview…</Card>}{pdfUrl && <iframe title="Saved resume preview" src={`${pdfUrl}#toolbar=0&navpanes=0&view=FitH`} className="mt-6 h-[1000px] w-full rounded-xl border bg-white" />}</ResumeShell>;
}

function formatDate(value: string) { return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)); }
function Notice({ children }: { children: ReactNode }) { return <p className="mt-5 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800" role="alert">{children}</p>; }
