"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ArrowRight, ArrowUpRight, Check, CircleAlert, Download, FileText, LoaderCircle, RefreshCw, Save, ShieldCheck, Upload, X } from "lucide-react";
import { gsap } from "gsap";
import { useGSAP } from "@gsap/react";
import { SiteHeader } from "@/components/site-header";
import { ApiError, apiBaseUrl, apiRequest } from "@/lib/api";

gsap.registerPlugin(useGSAP);
type CheckResult = { id: string; title: string; passed: boolean; weight: number; detail: string; suggestion: string; evidence: string[] };
type Review = { text: string; score: number; word_count: number; method: string; checks: CheckResult[]; skills: string[]; sections: { key: string; title: string; text: string }[]; job_match: { matched: string[]; missing: string[]; coverage: number | null; note: string } };

export function ReviewWorkspace() {
  const root = useRef<HTMLDivElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const resultsHeading = useRef<HTMLHeadingElement>(null);
  const [text, setText] = useState("");
  const [job, setJob] = useState("");
  const [filename, setFilename] = useState("");
  const [name, setName] = useState("My resume");
  const [result, setResult] = useState<Review | null>(null);
  const [analyzedJob, setAnalyzedJob] = useState("");
  const [busy, setBusy] = useState<"extract" | "review" | "save" | "export" | null>(null);
  const [error, setError] = useState("");
  const [needsLogin, setNeedsLogin] = useState(false);
  const [saved, setSaved] = useState("");
  const [dragging, setDragging] = useState(false);
  const [storageNote, setStorageNote] = useState("");
  const dirty = !!result && (text !== result.text || job !== analyzedJob);
  useEffect(() => {
    try {
      const draft = sessionStorage.getItem("careerpilot-review-draft");
      if (draft) {
        const parsed = JSON.parse(draft);
        if (typeof parsed.text === "string") setText(parsed.text.slice(0, 60000));
        if (typeof parsed.job === "string") setJob(parsed.job.slice(0, 20000));
        if (typeof parsed.name === "string") setName(parsed.name.slice(0, 160));
        sessionStorage.removeItem("careerpilot-review-draft");
        setStorageNote("Your unsaved text was restored for this tab. Run a check to continue.");
      }
    } catch { /* Browser storage may be disabled. The workspace still works. */ }
  }, []);
  useGSAP(() => {
    if (!result) return;
    const media = gsap.matchMedia();
    media.add("(prefers-reduced-motion: no-preference)", () => {
      gsap.from(".result-reveal", { y: 15, opacity: 0, stagger: 0.06, duration: 0.45, ease: "power2.out" });
    });
    return () => media.revert();
  }, { scope: root, dependencies: [result], revertOnUpdate: true });

  async function upload(file?: File) {
    if (!file || busy) return;
    setError(""); setSaved("");
    if (!/\.(pdf|docx|txt)$/i.test(file.name) || file.size > 3 * 1024 * 1024 || !file.size) {
      setError("Choose a PDF, DOCX, or TXT file smaller than 3 MB."); return;
    }
    setBusy("extract");
    try {
      const body = new FormData(); body.append("file", file);
      const extracted = await apiRequest<{ text: string }>("/review/extract", { method: "POST", body, signal: AbortSignal.timeout(45000) });
      setText(extracted.text); setFilename(file.name); setResult(null); setName(file.name.replace(/\.[^.]+$/, "").slice(0, 160));
    } catch (caught) { setError(caught instanceof ApiError ? caught.message : "We couldn’t read the file. Try again, or paste its text below."); }
    finally { setBusy(null); if (fileInput.current) fileInput.current.value = ""; }
  }
  async function evaluate() {
    setBusy("review"); setError(""); setSaved("");
    try {
      const review = await apiRequest<Review>("/review", { method: "POST", body: JSON.stringify({ text: text.trim(), job_description: job }), signal: AbortSignal.timeout(30000) });
      setText(review.text); setResult(review); setAnalyzedJob(job);
      requestAnimationFrame(() => resultsHeading.current?.focus({ preventScroll: true }));
    } catch (caught) { setError(caught instanceof ApiError ? caught.message : "Couldn’t run the check. Please retry in a moment."); }
    finally { setBusy(null); }
  }
  function retainDraft() {
    try { sessionStorage.setItem("careerpilot-review-draft", JSON.stringify({ text, job, name })); } catch { setStorageNote("Browser storage is unavailable. Download your text before leaving this page."); }
  }
  async function save() {
    setBusy("save"); setError(""); setNeedsLogin(false);
    try {
      const resume = await apiRequest<{ id: string }>("/review/save", { method: "POST", body: JSON.stringify({ text, job_description: job, name }) });
      setSaved(resume.id);
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 401) { setNeedsLogin(true); retainDraft(); }
      else setError(caught instanceof Error ? caught.message : "Could not save your resume.");
    } finally { setBusy(null); }
  }
  async function exportPdf() {
    setBusy("export"); setError("");
    try {
      const response = await fetch(`${apiBaseUrl}/review/pdf`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, job_description: "" }), signal: AbortSignal.timeout(30000) });
      if (!response.ok) { const body = await response.json().catch(() => null); throw new Error(typeof body?.detail === "string" ? body.detail : "Could not export your resume."); }
      const url = URL.createObjectURL(await response.blob());
      const anchor = document.createElement("a"); anchor.href = url; anchor.download = "resume.pdf"; anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not export your resume."); }
    finally { setBusy(null); }
  }
  function clear() { setText(""); setFilename(""); setResult(null); setSaved(""); setError(""); setNeedsLogin(false); setJob(""); setStorageNote(""); try { sessionStorage.removeItem("careerpilot-review-draft"); } catch {} }

  return <div className="product-site" ref={root}><SiteHeader /><main id="main-content" className="page-width review-main">
    <div className="review-title"><div><p className="eyebrow">YOUR EXPERIENCE. A CLEARER PICTURE.</p><h1>A stronger resume<br />starts right here<span className="brand-dot">.</span></h1><p>Bring what you have. We’ll help you find the next improvement.</p></div><span className="privacy-pill"><ShieldCheck size={16} /> Files aren’t stored. Saving is your choice.</span></div>
    <ol className="workflow-steps" aria-label="Resume review steps"><li className="active"><span>1</span> Bring your resume</li><li className={result ? "active" : ""}><span>2</span> Find the improvements</li><li className={saved ? "active" : ""}><span>3</span> Make your next move</li></ol>
    {error && <div className="workspace-alert" role="alert"><CircleAlert size={19} /><span>{error}</span><button aria-label="Dismiss error" onClick={() => setError("")}><X size={17} /></button></div>}
    {storageNote && <p className="workspace-notice" role="status">{storageNote}</p>}
    <div className="review-grid"><section className="workspace-panel">
      <div className="panel-heading"><div><p className="eyebrow">01 / YOUR STARTING POINT</p><h2>Your resume</h2></div>{text && <button className="quiet-button" onClick={clear} disabled={!!busy}>Start over <X size={14} /></button>}</div>
      <div className={`upload-zone ${dragging ? "drag-active" : ""}`} onDragOver={event => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={event => { event.preventDefault(); setDragging(false); void upload(event.dataTransfer.files[0]); }}>
        <input ref={fileInput} type="file" className="sr-only" accept=".pdf,.docx,.txt" aria-label="Upload your resume" disabled={!!busy} onChange={event => void upload(event.target.files?.[0])} />
        <span className="upload-icon">{busy === "extract" ? <LoaderCircle className="animate-spin" /> : <Upload />}</span>
        <h3>{busy === "extract" ? "Reading your resume…" : filename || "Your next chapter. Drop it here."}</h3><p>PDF, DOCX, or TXT · up to 3 MB · text-based files</p><button className="secondary-cta" type="button" disabled={!!busy} onClick={() => fileInput.current?.click()}>{filename ? "Choose a different file" : "Choose my resume"} <ArrowUpRight size={15} /></button>
      </div>
      <label className="editor-label" htmlFor="resume-text">{text ? "Review and edit your extracted text" : "Or paste your resume text"}<span>{text.length.toLocaleString()} / 60,000</span></label><textarea id="resume-text" className="resume-textarea" value={text} maxLength={60000} disabled={!!busy} onChange={event => { setText(event.target.value); setSaved(""); }} placeholder="Paste your existing resume here. No need to fill in individual fields." />
      <details className="job-details"><summary>Have a role in mind? <span>Add a job description</span></summary><label className="sr-only" htmlFor="job-description">Job description</label><textarea id="job-description" value={job} maxLength={20000} disabled={!!busy} onChange={event => setJob(event.target.value)} placeholder="Paste the job description to compare recognized skills…" /><p>We compare known skill terms. This doesn’t determine eligibility or predict hiring decisions.</p></details>
      <button className="primary-cta check-button" disabled={!!busy || text.trim().length < 80} onClick={() => void evaluate()}>{busy === "review" ? <><LoaderCircle size={18} className="animate-spin" /> Checking your resume…</> : <>{result ? "Check my changes" : "Show me the improvements"} <ArrowRight size={18} /></>}</button>
      <p className="input-hint">{text.trim().length < 80 ? "Add at least 80 characters to get started." : "Your text is sent securely to our API for rule-based analysis. No external AI service is used."}</p>
    </section>
    <section className="results-column" aria-label="Resume feedback"><h2 ref={resultsHeading} tabIndex={-1} className="sr-only">Resume check results</h2>{!result ? <div className="feedback-empty"><div className="empty-graphic"><FileText size={45} strokeWidth={1.2} /><span><Check size={17} /></span></div><p className="eyebrow">CLARITY IS ON THE OTHER SIDE.</p><h2>Less guesswork.<br />A better next draft.</h2><p>Your feedback will appear here. You’ll see what’s working, what to improve, and the evidence behind each check.</p><ul><li><Check size={16} /> Structure & readability checks</li><li><Check size={16} /> Action-led writing & measurable impact</li><li><Check size={16} /> Optional job-description skill comparison</li></ul><span className="no-signup-note">No signup. No made-up experience. Just a starting point.</span></div> : <>
      <div className="score-panel result-reveal"><div><p className="eyebrow">EVIDENCE, NOT A SCORE</p><h2>A closer look at your experience.</h2><p>{result.checks.filter(check => !check.passed).length} areas to review · {result.word_count} words</p></div><p className="score-explainer">Review the evidence and decide which edits strengthen your story. These English-language checks do not measure candidate quality, establish eligibility, or predict hiring outcomes. Dates and software versions do not count as impact metrics.</p></div>
      {dirty && <div className="workspace-notice" role="status"><RefreshCw size={16} /> Your text or target role changed. Run a new check for updated feedback.</div>}
      <div className="checks-panel result-reveal"><div className="panel-heading"><h2>Your next improvements</h2><span>{result.checks.filter(check => !check.passed).length} to review</span></div>{[...result.checks].sort((a, b) => Number(a.passed) - Number(b.passed)).map(check => <details className={`feedback-check ${check.passed ? "check-passed" : ""}`} key={check.id}><summary><span className="check-state">{check.passed ? <Check size={15} /> : <ArrowUpRight size={15} />}</span><span>{check.title}<small>{check.passed ? "Evidence found" : "Worth a closer look"}</small></span></summary><div className="check-description"><p>{check.detail}</p>{!check.passed && <p>{check.suggestion}</p>}{check.evidence.map((line, index) => <blockquote key={index}>{line}</blockquote>)}</div></details>)}</div>
      {job.trim() && <div className="workspace-panel result-reveal skill-panel"><p className="eyebrow">THE ROLE YOU HAVE IN MIND</p><h2>Skill term coverage {result.job_match.coverage !== null && <span>{result.job_match.coverage}%</span>}</h2><p>{result.job_match.note}</p>{result.job_match.coverage === null ? <p>No terms from our skill dictionary were found in the job description. Compare its requirements manually.</p> : <><h3>Found in your resume</h3><div className="skill-tags">{result.job_match.matched.length ? result.job_match.matched.map(skill => <span key={skill}>{skill}</span>) : <small>No matching skill terms found.</small>}</div><h3>Not detected — include only if true</h3><div className="skill-tags missing">{result.job_match.missing.length ? result.job_match.missing.map(skill => <span key={skill}>{skill}</span>) : <small>All recognized job skill terms were found.</small>}</div></>}</div>}
      <div className="workspace-panel save-panel result-reveal"><p className="eyebrow">02 / KEEP YOUR MOMENTUM</p><h2>Make this version yours.</h2><p>Edit your text on the left, check it again, then export or save it. Exports reformat the text; the original file’s layout is not retained.</p><label htmlFor="resume-name">Resume name</label><input id="resume-name" value={name} maxLength={160} onChange={event => setName(event.target.value)} /><div className="save-actions"><button className="primary-cta" onClick={() => void exportPdf()} disabled={!!busy}>{busy === "export" ? <LoaderCircle className="animate-spin" size={16} /> : <Download size={16} />} Download PDF</button><button className="secondary-cta" disabled={!!busy || !name.trim() || !!saved} onClick={() => void save()}>{busy === "save" ? <LoaderCircle className="animate-spin" size={16} /> : <Save size={16} />}{saved ? "Saved" : "Save to my resumes"}</button></div>{needsLogin && <div className="workspace-notice" role="status">Sign in to save your resume. <Link href="/login" onClick={retainDraft}>Sign in</Link> or <Link href="/signup" onClick={retainDraft}>create an account</Link>, then return to Resume check. Your draft stays in this tab for the redirect.</div>}{saved && <p className="saved-notice" role="status"><Check size={16} /> Saved to your private workspace. <Link href={`/resumes/${saved}`}>Open resume <ArrowRight size={14} /></Link></p>}</div>
    </>}</section></div>
  </main><footer className="review-footer page-width"><p><ShieldCheck size={15} /> Uploaded files are processed temporarily and discarded. Resume text is saved only when you choose Save.</p><Link href="/privacy">Privacy details <ArrowUpRight size={13} /></Link></footer></div>;
}
