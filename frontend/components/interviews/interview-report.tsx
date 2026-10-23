"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { RotateCcw, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { apiRequest } from "@/lib/api";
import { InterviewError, InterviewShell } from "./interview-shell";
import type { Interview } from "./types";

function FeedbackList({ title, items }: { title: string; items: string[] }) {
  return <section><h3 className="text-sm font-semibold">{title}</h3>{items.length ? <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-7 text-muted">{items.map((item, index) => <li key={index}>{item}</li>)}</ul> : <p className="mt-2 text-sm text-muted">No findings recorded.</p>}</section>;
}
export default function InterviewReport({ id }: { id: string }) {
  const router = useRouter();
  const [session, setSession] = useState<Interview | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController(); setError("");
    void apiRequest<Interview>(`/interviews/${id}`, { signal: controller.signal }).then(setSession).catch(caught => { if (!controller.signal.aborted) setError(caught instanceof Error ? caught.message : "Could not load the report."); });
    return () => controller.abort();
  }, [id, attempt]);
  async function retake() {
    setBusy(true); setError("");
    try { const value = await apiRequest<Interview>(`/interviews/${id}/retake`, { method: "POST" }); router.push(`/interviews/${value.id}`); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Could not start a retake."); setBusy(false); }
  }
  async function remove() {
    if (!window.confirm("Delete this interview and all its saved answers and feedback?")) return;
    setBusy(true); setError("");
    try { await apiRequest(`/interviews/${id}`, { method: "DELETE" }); router.push("/interviews"); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Could not delete this interview."); setBusy(false); }
  }
  return <InterviewShell title={session ? `${session.role} · Your practice report` : "Opening your report…"} description="See what worked, where your answer lost precision, and what to practice next. Your report is private to your account.">
    {error && <InterviewError>{error} <button className="underline" onClick={() => setAttempt(current => current + 1)}>Retry report</button> <Link className="ml-2 underline" href="/login">Sign in</Link></InterviewError>}
    {!session ? !error && <Card className="p-8" role="status">Loading report…</Card> : <>
      {session.status !== "completed" && <p className="mb-5 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm">This interview is still {session.status}. <Link className="underline" href={`/interviews/${id}`}>Return to the room</Link> to continue or end it. Scores below cover submitted answers only.</p>}
      <Card className="p-6 sm:p-8"><div className="flex flex-wrap items-center justify-between gap-5"><div><p className="text-xs font-semibold uppercase tracking-widest text-brand">Overall practice score</p><p className="mt-3 text-5xl font-semibold tracking-tight text-brand">{session.report.score === null ? "Not scored" : <>{session.report.score}<span className="text-xl text-muted"> / 100</span></>}</p><p className="mt-3 text-sm text-muted">{session.report.answered} of {session.report.planned} questions answered · {session.interview_type} · starting/last difficulty {session.difficulty}/5</p></div><div className="flex flex-wrap gap-3"><Button disabled={busy} onClick={() => void retake()}><RotateCcw size={16} aria-hidden />{busy ? "Please wait…" : "Retake with fresh questions"}</Button><Button variant="ghost" disabled={busy} onClick={() => void remove()}><Trash2 size={16} aria-hidden />Delete interview</Button></div></div><p className="mt-5 max-w-3xl text-xs leading-6 text-muted">{session.report.note} Model: {session.model}. The overall score averages the three rubric dimensions across submitted answers; unattempted questions are not scored.</p>
        <div className="mt-6 grid gap-4 sm:grid-cols-3">{([['accuracy', 'Accuracy / completeness'], ['relevance', 'Relevance'], ['clarity', 'Clarity']] as const).map(([key, label]) => <div key={key} className="rounded-xl border p-4"><p className="text-sm font-medium">{label}</p><p className="mt-2 text-xl font-semibold">{session.report[key] ?? "—"}</p><meter aria-label={label} min={0} max={100} value={session.report[key] ?? 0} className="mt-2 h-3 w-full" /></div>)}</div>
      </Card>
      <div className="mt-6 grid gap-6 lg:grid-cols-3"><Card className="p-6"><FeedbackList title="Strengths to keep" items={session.report.strengths} /></Card><Card className="p-6"><FeedbackList title="Areas to improve" items={session.report.weaknesses} /></Card><Card className="p-6"><FeedbackList title="Your revision plan" items={session.report.recommendations} /></Card></div>
      <section className="mt-10"><h2 className="text-xl font-semibold">Question-by-question review</h2><div className="mt-5 space-y-5">{session.turns.map((turn, index) => <Card className="p-6 sm:p-8" key={turn.id}><p className="text-xs font-semibold uppercase tracking-wider text-brand">Question {index + 1} · {turn.category} · difficulty {turn.difficulty}/5</p><h3 className="mt-3 text-lg font-semibold leading-7">{turn.text}</h3><div className="mt-5 rounded-xl bg-slate-50 p-4"><p className="text-xs font-semibold uppercase tracking-wide">Your answer</p><p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-muted">{turn.answer || "Not submitted — this question was not scored."}</p></div>{turn.evaluation && <><p className="mt-5 text-sm font-semibold">{turn.evaluation.score}/100 · Accuracy {turn.evaluation.accuracy} · Relevance {turn.evaluation.relevance} · Clarity {turn.evaluation.clarity}</p><p className="mt-3 text-sm leading-7 text-muted">{turn.evaluation.feedback}</p><div className="mt-5 grid gap-6 sm:grid-cols-2"><FeedbackList title="What worked" items={turn.evaluation.strengths} /><FeedbackList title="Missing or unclear" items={turn.evaluation.weaknesses} /><FeedbackList title="Corrections" items={turn.evaluation.corrections} /><FeedbackList title="Practice next" items={turn.evaluation.recommendations} /></div><details className="mt-6 rounded-xl border p-4"><summary className="text-sm font-semibold">Sample answer / suggested structure</summary><p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-muted">{turn.evaluation.sample_answer}</p><p className="mt-3 text-xs leading-6 text-muted">Check the AI’s technical suggestions. Replace hypothetical examples with your own verified experience.</p></details></>}</Card>)}</div></section>
    </>}
  </InterviewShell>;
}
