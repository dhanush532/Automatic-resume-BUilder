"use client";

import Link from "next/link";
import { useRef } from "react";
import { ArrowDown, ArrowRight, ArrowUpRight, Check, FileCheck2, Layers3, ScanLine, ShieldCheck, Sparkles, Upload } from "lucide-react";
import { gsap } from "gsap";
import { useGSAP } from "@gsap/react";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { SiteHeader } from "@/components/site-header";

gsap.registerPlugin(useGSAP, ScrollTrigger);

export function LandingPage() {
  const root = useRef<HTMLDivElement>(null);
  useGSAP(() => {
    const media = gsap.matchMedia();
    media.add("(prefers-reduced-motion: no-preference)", () => {
      gsap.timeline({ defaults: { ease: "power3.out", duration: 0.8 } })
        .from(".hero-reveal", { y: 28, opacity: 0, stagger: 0.11 })
        .from(".resume-scene", { y: 35, opacity: 0, rotation: 2 }, "-=0.7")
        .from(".scene-note", { y: 16, opacity: 0, stagger: 0.12 }, "-=0.35");
      gsap.utils.toArray<HTMLElement>(".scroll-reveal").forEach((element) => {
        gsap.from(element, { y: 26, opacity: 0, duration: 0.65, scrollTrigger: { trigger: element, start: "top 90%", once: true } });
      });
    });
    return () => media.revert();
  }, { scope: root });

  return <div ref={root} className="product-site">
    <SiteHeader />
    <main id="main-content">
      <section className="landing-hero page-width">
        <div className="hero-copy">
          <div className="hero-reveal eyebrow"><span className="live-dot" /> YOUR NEXT CHAPTER STARTS HERE</div>
          <h1 className="hero-reveal">Good experience.<br />Better resume.<br /><span>More possibility.</span></h1>
          <p className="hero-reveal hero-description">You’ve already done the hard work. Drop in your resume, find what’s holding it back, and make your next move with confidence.</p>
          <div className="hero-reveal hero-actions"><Link href="/review" className="primary-cta">Give my resume a check <ArrowUpRight size={20} aria-hidden="true" /></Link><a href="#how-it-works" className="text-link">See how it works <ArrowDown size={16} aria-hidden="true" /></a></div>
          <div className="hero-reveal hero-proof"><span><Check size={15} /> No signup to check</span><span><Check size={15} /> No lengthy forms</span><span><Check size={15} /> PDF & DOCX</span></div>
        </div>
        <div className="resume-scene" aria-label="Illustration of the resume review process">
          <div className="scene-orbit" aria-hidden="true" />
          <div className="scene-label"><span className="live-dot" /> A LITTLE CLARITY GOES A LONG WAY</div>
          <div className="resume-paper" aria-hidden="true"><div className="paper-top"><div className="paper-avatar">YOU</div><span>YOUR NEXT OPPORTUNITY<br /><b>Starts with your story.</b></span></div><div className="paper-rule" /><div className="paper-heading">EXPERIENCE</div><div className="paper-line long" /><div className="paper-line" /><div className="paper-line short" /><div className="paper-highlight"><Check size={15} /> Show the impact. Not just the task.</div><div className="paper-heading">PROJECTS & SKILLS</div><div className="paper-line" /><div className="paper-line long" /><div className="paper-tags"><span>Your work</span><span>Your strengths</span><span>Your story</span></div><div className="paper-line short" /><div className="paper-line" /></div>
          <div className="scene-note note-top"><span className="note-icon"><ScanLine size={18} /></span><div><b>Your resume, decoded.</b><small>Clear feedback. Real next steps.</small></div></div>
          <div className="scene-note note-bottom"><span className="note-icon mint"><Sparkles size={18} /></span><div><b>Less filling. More moving.</b><small>Start with what you already have.</small></div><ArrowUpRight size={18} /></div>
          <span className="scene-caption">An illustration of the workflow, not a sample result.</span>
        </div>
      </section>
      <div className="value-strip"><div className="page-width"><span>BUILT FOR YOUR NEXT MOVE</span><p><FileCheck2 size={19} /> Evidence-based feedback</p><p><Layers3 size={19} /> Saved resume versions</p><p><ShieldCheck size={19} /> You control what’s saved</p></div></div>
      <section id="how-it-works" className="page-width steps-section">
        <div className="section-heading scroll-reveal"><div><p className="eyebrow">LESS ADMIN. MORE MOMENTUM.</p><h2>Your resume already<br />has a story. Let’s sharpen it.</h2></div><p>No retyping your entire career. No twelve-section questionnaire. Just a clearer path from what you have to what’s next.</p></div>
        <div className="steps-grid">{[
          { icon: Upload, number: "01", title: "Drop it in.", text: "Upload your PDF or DOCX, or paste the text. Review the extracted content before you use it." },
          { icon: ScanLine, number: "02", title: "Find your next fix.", text: "See checks for structure, action-led writing, and measurable impact. Add a job description to compare recognized skills." },
          { icon: ArrowUpRight, number: "03", title: "Make your move.", text: "Edit the text, run another check, and download a clean resume. Sign in when you’re ready to save versions." },
        ].map(({ icon: Icon, number, title, text }) => <article className="step-card scroll-reveal" key={number}><div className="step-top"><Icon size={25} strokeWidth={1.6} aria-hidden="true" /><span>{number}</span></div><h3>{title}</h3><p>{text}</p></article>)}</div>
      </section>
      <section className="page-width"><div className="honest-section scroll-reveal"><div><p className="eyebrow">USEFUL FEEDBACK. NO MAGIC NUMBERS.</p><h2>A second pair of eyes.<br />Not a crystal ball.</h2><p>Every readiness check tells you what we found and why it matters. No guaranteed interviews, made-up experience, or mysterious “ATS success” scores.</p><Link href="/review" className="text-link">See what your resume says <ArrowRight size={17} /></Link></div><div className="honest-list">{["Start with a resume, not an empty form", "See the evidence behind each check", "Compare skills against a job description", "Keep every claim true to your experience"].map(item => <p key={item}><span><Check size={17} /></span>{item}</p>)}</div></div></section>
      <section className="page-width final-cta scroll-reveal"><span className="eyebrow">ONE SMALL STEP. A CLEARER NEXT CHAPTER.</span><h2>Your next move<br />looks good on you.</h2><Link href="/review" className="primary-cta">Let’s start with your resume <ArrowUpRight size={20} /></Link><p>No account needed for your first check.</p></section>
    </main>
    <footer className="site-footer page-width"><Link className="wordmark" href="/">careerpilot<span className="brand-dot">.</span></Link><p>Built for the work you want to do next.</p><div><Link href="/privacy">Privacy</Link><Link href="/terms">Terms</Link><Link href="/login">Sign in <ArrowUpRight size={13} /></Link></div></footer>
  </div>;
}
