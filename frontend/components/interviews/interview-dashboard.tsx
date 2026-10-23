"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ArrowUpRight, FileText, Mic, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ApiError, apiRequest } from "@/lib/api";
import { InterviewError, InterviewShell } from "./interview-shell";
import { interviewTypes, type Interview } from "./types";

type SavedResume = { id: string; name: string };
const selectStyle = "mt-2 h-11 w-full rounded-lg border bg-white px-3 text-sm";

export default function InterviewDashboard() {
  const router = useRouter();
  const [resumes, setResumes] = useState<SavedResume[]>([]);
  const [history, setHistory] = useState<Interview[]>([]);
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [needsLogin, setNeedsLogin] = useState(false);
  const [busy, setBusy] = useState(false);
  const [source, setSource] = useState("saved");
  const [resumeId, setResumeId] = useState("");
  const [text, setText] = useState("");
  const [role, setRole] = useState("");
  const [job, setJob] = useState("");
  const [kind, setKind] = useState("mixed");
  const [level, setLevel] = useState(2);
  const [duration, setDuration] = useState(15);
  const [count, setCount] = useState(5);
  const [more, setMore] = useState(true);
  const load = useCallback(async (signal?: AbortSignal) => {
    setError(""); setLoading(true);
    try {
      const [caps, items, sessions] = await Promise.all([
        apiRequest<{ configured: boolean }>("/interviews/capabilities", { signal }),
        apiRequest<SavedResume[]>("/resumes", { signal }), apiRequest<Interview[]>("/interviews", { signal }),
      ]);
      setConfigured(caps.configured); setResumes(items); setHistory(sessions); setMore(sessions.length === 50);
      setResumeId(current => current || items[0]?.id || ""); setNeedsLogin(false);
    } catch (caught) {
      if (!signal?.aborted) { setError(caught instanceof Error ? caught.message : "Could not load your interview workspace."); setNeedsLogin(caught instanceof ApiError && caught.status === 401); }
    } finally { if (!signal?.aborted) setLoading(false); }
  }, []);
  useEffect(() => { const controller = new AbortController(); void load(controller.signal); return () => controller.abort(); }, [load]);
  async function upload(file?: File) {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf") || file.size > 3 * 1024 * 1024) { setError("Choose a text-based PDF smaller than 3 MB."); return; }
    setBusy(true); setError("");
    try { const form = new FormData(); form.append("file", file); const result = await apiRequest<{ text: string }>("/interviews/extract", { method: "POST", body: form }); setText(result.text); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Could not read this PDF."); }
    finally { setBusy(false); }
  }
  async function start() {
    setBusy(true); setError("");
    try {
      const session = await apiRequest<Interview>("/interviews", { method: "POST", body: JSON.stringify({
        role, job_description: job, interview_type: kind, difficulty: level, duration_minutes: duration,
        question_count: count, ...(source === "saved" ? { resume_id: resumeId } : { resume_text: text }),
      }) }); router.push(`/interviews/${session.id}`);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not start your interview."); setBusy(false); }
  }
  async function loadMore() {
    setBusy(true); setError("");
    try { const items = await apiRequest<Interview[]>(`/interviews?offset=${history.length}`); setHistory(current => [...current, ...items]); setMore(items.length === 50); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Could not load history."); }
    finally { setBusy(false); }
  }
  const completed = history.filter(item => item.status === "completed" && item.report.score !== null).slice(0, 12).reverse();
  return <InterviewShell title="Your next interview starts here." description="Turn your resume into a focused practice session. Answer in your own words, explore follow-ups, and leave with a specific plan for your next attempt.">
    {error && <InterviewError>{error} {needsLogin ? <Link className="underline" href="/login">Sign in with your existing account</Link> : <button className="ml-2 underline" onClick={() => void load()}>Reload workspace</button>}</InterviewError>}
    {loading ? <Card className="p-8" role="status">Loading your resumes and interview history…</Card> : <>
      {configured === false && <div role="status" className="mb-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">AI interviews need a backend Gemini API key. Configure GEMINI_API_KEY to start; saved history remains available.</div>}
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]">
        <Card className="p-6 sm:p-8"><div className="flex items-center gap-3"><span className="rounded-xl bg-lime-100 p-3 text-brand"><Mic size={23} aria-hidden /></span><div><h2 className="text-xl font-semibold">Build your practice session</h2><p className="mt-1 text-xs text-muted">One question at a time. Feedback grounded in your answer.</p></div></div>
          <form className="mt-7 space-y-5" onSubmit={event => { event.preventDefault(); void start(); }}>
            <fieldset><legend className="text-sm font-semibold">Resume source</legend><div className="mt-3 flex flex-wrap gap-4 text-sm"><label className="flex min-h-11 items-center gap-2"><input type="radio" name="source" checked={source === "saved"} onChange={() => setSource("saved")} />Saved resume</label><label className="flex min-h-11 items-center gap-2"><input type="radio" name="source" checked={source === "upload"} onChange={() => setSource("upload")} />Upload PDF / paste text</label></div>
              {source === "saved" ? <label className="mt-3 block text-sm">Choose a resume<select required className={selectStyle} value={resumeId} onChange={event => setResumeId(event.target.value)}><option value="">Select your resume</option>{resumes.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select>{!resumes.length && <span className="mt-2 block text-xs text-muted">No resumes yet. Upload a PDF here or <Link className="underline" href="/resumes/new">create a resume</Link>.</span>}</label> : <div className="mt-3 rounded-xl border border-dashed p-4"><label className="flex items-center gap-2 text-sm font-medium"><Upload size={16} aria-hidden />Upload resume PDF<input className="min-w-0 flex-1 text-xs" type="file" accept=".pdf,application/pdf" disabled={busy} onChange={event => void upload(event.target.files?.[0])} /></label><label className="mt-4 block text-sm">Resume text<textarea required minLength={80} maxLength={60000} className="mt-2 min-h-40 w-full rounded-lg border p-3 text-sm leading-6" value={text} onChange={event => setText(event.target.value)} /></label><p className="mt-2 text-xs leading-5 text-muted">Text-based PDFs only. Scanned documents need OCR first. Review the extracted text before starting.</p></div>}
            </fieldset>
            <label className="block text-sm font-medium">Target job role<Input required minLength={2} maxLength={160} className="mt-2" placeholder="e.g. Backend engineer" value={role} onChange={event => setRole(event.target.value)} /></label>
            <label className="block text-sm font-medium">Job description (optional)<textarea maxLength={12000} className="mt-2 min-h-28 w-full rounded-lg border p-3 text-sm" value={job} onChange={event => setJob(event.target.value)} placeholder="Add the responsibilities and requirements you want to practice." /></label>
            <div className="grid gap-4 sm:grid-cols-2"><label className="text-sm font-medium">Interview type<select className={selectStyle} value={kind} onChange={event => setKind(event.target.value)}>{interviewTypes.map(type => <option key={type} value={type}>{type === "hr" ? "HR" : `${type[0].toUpperCase()}${type.slice(1)}`}</option>)}</select></label><label className="text-sm font-medium">Starting difficulty<select className={selectStyle} value={level} onChange={event => setLevel(Number(event.target.value))}>{["Entry", "Junior", "Mid-level", "Senior", "Staff"].map((label, index) => <option key={label} value={index + 1}>{label}</option>)}</select></label><label className="text-sm font-medium">Duration (minutes)<Input className="mt-2" required type="number" min={5} max={90} value={duration} onChange={event => setDuration(Number(event.target.value))} /></label><label className="text-sm font-medium">Question count (including follow-ups)<Input className="mt-2" required type="number" min={1} max={20} value={count} onChange={event => setCount(Number(event.target.value))} /></label></div>
            <p className="rounded-lg bg-slate-50 p-3 text-xs leading-6 text-muted">Starting sends career evidence and the optional job description to Google Gemini. Contact headers are omitted and common contact patterns are redacted. Typed/dictated answers are sent for evaluation. Your camera stays local; no webcam recording is stored. Browser dictation may use your browser provider’s speech service.</p>
            <Button type="submit" disabled={busy || configured !== true || role.trim().length < 2 || (source === "saved" ? !resumeId : text.trim().length < 80)}>{busy ? "Preparing your session…" : "Start interview"}<ArrowUpRight size={16} aria-hidden /></Button>
          </form>
        </Card>
        <div className="space-y-6"><Card className="p-6"><h2 className="text-lg font-semibold">Practice, reflect, repeat.</h2><ol className="mt-5 space-y-5 text-sm leading-6 text-muted"><li><strong className="block text-brand">01 / Bring your own evidence</strong>Questions connect your projects and experience to the target role.</li><li><strong className="block text-brand">02 / Make it a conversation</strong>Use voice or text. Follow-ups adapt to your recent answers.</li><li><strong className="block text-brand">03 / Leave with a revision plan</strong>Review corrections, sample answers and targeted recommendations.</li></ol></Card>
          <Card className="p-6"><h2 className="text-lg font-semibold">Your recent progress</h2><p className="mt-1 text-xs leading-5 text-muted">Latest 12 scored sessions in loaded history. Scores depend on the role, questions and difficulty.</p>{completed.length ? <><svg viewBox="0 0 320 140" role="img" aria-label={`Interview scores over time: ${completed.map(item => item.report.score).join(", ")}`} className="mt-5 w-full"><line x1="12" y1="120" x2="308" y2="120" stroke="#cbd5e1" /><polyline fill="none" stroke="#173c32" strokeWidth="3" points={completed.map((item, index) => `${12 + index * (296 / Math.max(1, completed.length - 1))},${120 - item.report.score!}`).join(" ")} />{completed.map((item, index) => <circle key={item.id} cx={12 + index * (296 / Math.max(1, completed.length - 1))} cy={120 - item.report.score!} r="4" fill="#173c32" />)}</svg><p className="text-xs text-muted">Older attempts → newer attempts · 0–100 practice scale</p></> : <p className="mt-6 text-sm leading-6 text-muted">Complete your first interview to start tracking progress.</p>}</Card></div>
      </div>
      <section className="mt-10"><div className="mb-5 flex items-center gap-2"><FileText size={20} aria-hidden /><h2 className="text-xl font-semibold">Interview history</h2></div>{history.length ? <div className="grid gap-4 sm:grid-cols-2">{history.map(item => <Card key={item.id} className="p-5"><div className="flex items-start justify-between gap-3"><h3 className="font-semibold">{item.role}</h3><span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs capitalize">{item.status}</span></div><p className="mt-2 text-xs leading-6 text-muted">{new Date(item.created_at).toLocaleString()} · {item.interview_type} · {item.report.answered}/{item.question_count} answered</p><div className="mt-4 flex items-center justify-between gap-3"><span className="text-sm font-semibold text-brand">{item.report.score === null ? "Not scored yet" : `${item.report.score}/100`}</span><Link className="inline-flex min-h-11 items-center gap-1 text-sm font-semibold text-brand underline" href={`/interviews/${item.id}${item.status === "completed" ? "/report" : ""}`}>{item.status === "completed" ? "View report" : "Continue session"}<ArrowUpRight size={15} aria-hidden /></Link></div></Card>)}</div> : <Card className="p-8 text-sm text-muted">No interviews yet. Your first session will appear here.</Card>}{more && <Button className="mt-5" variant="secondary" disabled={busy} onClick={() => void loadMore()}>Load older interviews</Button>}</section>
    </>}
  </InterviewShell>;
}
