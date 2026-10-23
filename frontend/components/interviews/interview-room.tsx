"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Camera, CameraOff, Mic, MicOff, Pause, Play, Volume2, Square, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ApiError, apiRequest } from "@/lib/api";
import { InterviewError, InterviewShell } from "./interview-shell";
import type { Interview } from "./types";
import { useInterviewMedia } from "./use-interview-media";

export default function InterviewRoom({ id }: { id: string }) {
  const router = useRouter();
  const [session, setSession] = useState<Interview | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [needsLogin, setNeedsLogin] = useState(false);
  const [busy, setBusy] = useState(false);
  const [remaining, setRemaining] = useState(0);
  const [ready, setReady] = useState(false);
  const busyRef = useRef(false);
  const timeoutHandled = useRef(false);
  const current = session?.turns.at(-1);
  const currentQuestion = useRef<string | undefined>(undefined);
  currentQuestion.current = current?.id;
  const answer = current ? drafts[current.id] ?? "" : "";
  const hasDraft = Object.values(drafts).some(value => value.trim());
  const media = useInterviewMedia(useCallback(text => {
    const questionId = currentQuestion.current;
    if (questionId) setDrafts(previous => ({ ...previous, [questionId]: `${previous[questionId] ?? ""} ${text}`.trim().slice(0, 12000) }));
  }, []));
  const stopAll = media.stopAll;
  function setAnswer(value: string) { if (current) setDrafts(previous => ({ ...previous, [current.id]: value })); }

  const load = useCallback(async (signal?: AbortSignal) => {
    stopAll();
    setError("");
    try { const value = await apiRequest<Interview>(`/interviews/${id}`, { signal }); setSession(value); setNeedsLogin(false); }
    catch (caught) { if (!signal?.aborted) { setError(caught instanceof Error ? caught.message : "Could not open this interview."); setNeedsLogin(caught instanceof ApiError && caught.status === 401); } }
  }, [id, stopAll]);
  useEffect(() => { const controller = new AbortController(); void load(controller.signal); return () => controller.abort(); }, [load]);
  useEffect(() => {
    if (!session) return;
    if (session.status === "completed") { stopAll(); router.replace(`/interviews/${id}/report`); return; }
    if (session.status === "paused") stopAll();
    const base = Date.now();
    function tick() {
      const seconds = session!.duration_minutes * 60 - session!.elapsed_seconds - (session!.status === "active" ? Math.floor((Date.now() - base) / 1000) : 0);
      setRemaining(Math.max(0, seconds)); setReady(true);
    }
    tick(); const timer = setInterval(tick, 1000); return () => clearInterval(timer);
  }, [session, id, router, stopAll]);
  useEffect(() => { if (ready && remaining === 0 && session?.status === "active" && !busy && !timeoutHandled.current) { timeoutHandled.current = true; stopAll(); void load(); } }, [ready, remaining, session?.status, busy, load, stopAll]);
  useEffect(() => {
    const guard = (event: BeforeUnloadEvent) => { if (hasDraft || session?.status === "active") event.preventDefault(); };
    window.addEventListener("beforeunload", guard); return () => window.removeEventListener("beforeunload", guard);
  }, [hasDraft, session?.status]);
  async function action(path: string, body?: object) {
    if (busyRef.current) return;
    busyRef.current = true; setBusy(true); setError("");
    media.stopSpeaking();
    try {
      const value = await apiRequest<Interview>(`/interviews/${id}/${path}`, { method: "POST", ...(body ? { body: JSON.stringify(body) } : {}) });
      setSession(value);
      if (path === "answers") setAnswer("");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Request failed. Your typed answer is kept; retry when the connection returns."); }
    finally { busyRef.current = false; setBusy(false); }
  }
  async function end() {
    if (!window.confirm("End this interview? Submitted answers will be included in your report. Any unsubmitted answer will not be scored.")) return;
    stopAll(); await action("control", { action: "end" });
  }
  const active = session?.status === "active" && remaining > 0;
  return <InterviewShell title={session ? `${session.role} · Interview room` : "Opening your interview…"} description="A focused conversation, one question at a time. Your camera is a local preview only; feedback is based on submitted answer text.">
    {error && <InterviewError>{error} {needsLogin && <Link href="/login" className="underline">Sign in</Link>} <button className="ml-2 underline" onClick={() => void load()}>Reload saved progress</button></InterviewError>}
    {Object.entries(drafts).filter(([questionId, value]) => questionId !== current?.id && value.trim()).map(([questionId, value]) => <details key={questionId} className="mb-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm"><summary className="font-medium">Unsubmitted draft from an earlier question</summary><p className="mt-2 text-xs leading-6">Saved progress advanced in another tab. This text has not been applied to the current question.</p><p className="mt-3 whitespace-pre-wrap leading-7">{value}</p></details>)}
    {!session ? !error && <Card className="p-8" role="status">Loading interview…</Card> : <>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-white p-4"><div className="flex flex-wrap items-center gap-4 text-sm"><span className="rounded-full bg-lime-100 px-3 py-1 capitalize text-brand">{session.status}</span><span>Question {session.turns.length} of {session.question_count}</span><span role="timer" aria-label="Time remaining" className="font-mono font-semibold">{Math.floor(remaining / 60)}:{String(remaining % 60).padStart(2, "0")} left</span></div><div className="flex gap-2"><Button variant="secondary" disabled={busy} onClick={() => { stopAll(); void action("control", { action: session.status === "paused" ? "resume" : "pause" }); }}>{session.status === "paused" ? <Play size={15} aria-hidden /> : <Pause size={15} aria-hidden />}{session.status === "paused" ? "Resume" : "Pause"}</Button><Button variant="ghost" disabled={busy} onClick={() => void end()}>End interview</Button></div></div>
      <progress aria-label="Interview progress" className="mb-6 h-2 w-full accent-[#173c32]" value={session.report.answered} max={session.question_count} />
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <div className="space-y-6"><Card className="p-6 sm:p-8"><div className="flex items-center gap-3"><span className={`flex h-12 w-12 items-center justify-center rounded-full bg-brand text-xs font-bold text-white ${media.speaking ? "ring-4 ring-lime-200" : ""}`} aria-hidden>AI</span><div><p className="text-sm font-semibold">Your AI interviewer</p><p className="text-xs text-muted" role="status">{media.speaking ? "Speaking…" : busy ? "Thinking…" : "Ready when you are"}</p></div></div>{current && <><p className="mt-6 text-xs font-semibold uppercase tracking-wider text-muted">{current.category} · difficulty {current.difficulty}/5</p><h2 className="mt-3 text-xl font-semibold leading-relaxed">{current.text}</h2><Button variant="ghost" className="mt-4" disabled={!active || busy || !media.voiceSupported} onClick={() => media.speaking ? media.stopSpeaking() : media.speak(current.text)}>{media.speaking ? <Square size={16} aria-hidden /> : <Volume2 size={16} aria-hidden />}{media.speaking ? "Stop speaking" : "Read question aloud"}</Button></>}</Card>
          {current?.evaluation ? <Card className="p-6"><p className="text-xs font-semibold uppercase tracking-wider text-brand">Answer saved · {current.evaluation.score}/100</p><h2 className="mt-3 text-lg font-semibold">A quick reflection</h2><p className="mt-3 text-sm leading-7 text-muted">{current.evaluation.feedback}</p><p className="mt-3 text-xs text-muted">Full corrections and a sample answer will be in your report.</p><Button className="mt-6" disabled={busy || !active} onClick={() => void action("next")}>{busy ? "Preparing follow-up…" : "Next question"}<ArrowRight size={16} aria-hidden /></Button></Card> : <Card className="p-6"><label htmlFor="interview-answer" className="text-lg font-semibold">Your answer</label><p className="mt-2 text-xs leading-6 text-muted">Dictate or type below. Review the transcript and stop dictation before submitting. Give specific examples and explain your reasoning.</p><textarea id="interview-answer" className="mt-4 min-h-[240px] w-full rounded-xl border p-4 text-sm leading-7" disabled={!active || busy} maxLength={12000} value={answer} onChange={event => setAnswer(event.target.value)} placeholder="Walk through your answer…" /><p className="mt-1 text-right text-xs text-muted">{answer.length}/12000</p>{media.interim && <p className="mt-3 rounded-lg bg-slate-50 p-3 text-sm text-muted" role="status">Live dictation (not final): {media.interim}</p>}<div className="mt-4 flex flex-wrap gap-3"><Button variant="secondary" disabled={!active || busy || !media.speechSupported} aria-pressed={media.listening} onClick={() => void media.toggleMicrophone()}>{media.listening ? <MicOff size={16} aria-hidden /> : <Mic size={16} aria-hidden />}{media.listening ? "Stop dictation" : "Dictate answer"}</Button><Button disabled={!active || busy || media.listening || !answer.trim()} onClick={() => current && void action("answers", { question_id: current.id, answer })}>{busy ? "Evaluating and saving…" : "Submit answer"}</Button></div>{!media.speechSupported && <p className="mt-3 text-xs leading-6 text-muted">Browser dictation is unavailable here. Text answers are fully supported.</p>}</Card>}
          {session.status === "paused" && <p className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm" role="status">Interview paused. The timer and media are stopped. Resume when you’re ready.</p>}
        </div>
        <div className="space-y-6"><Card className="overflow-hidden p-4"><div className="relative aspect-video overflow-hidden rounded-xl bg-[#173c32]"><video ref={media.video} autoPlay muted playsInline aria-label="Your local webcam preview" className={`h-full w-full object-cover ${media.camera ? "" : "invisible"}`} />{!media.camera && <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-white"><CameraOff size={30} aria-hidden /><span className="text-sm">Camera is off</span></div>}</div><Button className="mt-4 w-full" variant="secondary" disabled={!active || busy} aria-pressed={media.camera} onClick={() => void media.toggleCamera()}>{media.camera ? <CameraOff size={16} aria-hidden /> : <Camera size={16} aria-hidden />}{media.camera ? "Turn camera off" : "Enable camera"}</Button><p className="mt-3 text-xs leading-6 text-muted">Local preview only. Video and facial expressions are never used for scoring.</p>{media.error && <InterviewError>{media.error}</InterviewError>}</Card>
          <Card className="p-6"><h2 className="font-semibold">Conversation transcript</h2><p className="mt-2 text-xs leading-5 text-muted">Submitted questions and answers are saved. Unsubmitted text stays in this tab.</p><ol className="mt-4 max-h-[480px] space-y-5 overflow-y-auto">{session.turns.map((turn, index) => <li key={turn.id} className="border-b pb-4 text-sm leading-6"><p className="font-medium">Q{index + 1}. {turn.text}</p><p className="mt-2 whitespace-pre-wrap text-muted">{turn.answer || "Waiting for your answer…"}</p></li>)}</ol></Card>
        </div>
      </div>
    </>}
  </InterviewShell>;
}
