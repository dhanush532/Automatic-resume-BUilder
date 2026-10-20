"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, Check, ChevronDown, CircleAlert, Plus, Save, Trash2, X } from "lucide-react";

import { ApiError, apiRequest } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

type Profile = {
  id: string;
  full_name: string;
  headline: string | null;
  bio: string | null;
  location: string | null;
  linkedin_url: string | null;
  github_url: string | null;
  portfolio_url: string | null;
  profile_photo_key: string | null;
  other_links: Array<Record<string, string>>;
  email: string;
  username: string;
  phone: string | null;
};

type Preferences = {
  desired_job_titles: string[];
  industries: string[];
  preferred_locations: string[];
  work_arrangements: string[];
  employment_types: string[];
  expected_salary_min: string | number | null;
  expected_salary_max: string | number | null;
  salary_currency: string | null;
  willing_to_relocate: boolean | null;
  preferred_company_sizes: string[];
  company_preferences: string | null;
  exclusions: string[];
};

type PassportRecord = { id: string; [key: string]: unknown };
type Passport = {
  profile: Profile | null;
  career_preferences: Preferences | null;
  professional_links: PassportRecord[];
  education: PassportRecord[];
  skills: PassportRecord[];
  experience: PassportRecord[];
  projects: PassportRecord[];
  certifications: PassportRecord[];
  courses: PassportRecord[];
  achievements: PassportRecord[];
  languages: PassportRecord[];
  open_source_contributions: PassportRecord[];
  completeness: number;
};

type FieldType = "text" | "url" | "date" | "textarea" | "number" | "checkbox" | "select";
type FieldSpec = {
  name: string;
  label: string;
  type?: FieldType;
  required?: boolean;
  options?: Array<{ value: string; label: string }>;
  placeholder?: string;
};
type FormValue = string | boolean;

const listFields = (value: string[] | undefined) => (value ?? []).join(", ");
const parseList = (value: string) => value.split(",").map((item) => item.trim()).filter(Boolean);

const collectionDefinitions: Array<{
  key: keyof Pick<Passport, "professional_links" | "education" | "skills" | "experience" | "projects" | "certifications" | "courses" | "achievements" | "languages" | "open_source_contributions">;
  endpoint: string;
  title: string;
  description: string;
  fields: FieldSpec[];
  summary: (record: PassportRecord) => string;
}> = [
  {
    key: "professional_links",
    endpoint: "links",
    title: "Professional links",
    description: "Add the public profiles and sites you choose to share.",
    fields: [
      { name: "label", label: "Label", required: true, placeholder: "Portfolio" },
      { name: "url", label: "URL", type: "url", required: true, placeholder: "https://" },
    ],
    summary: (record) => `${String(record.label)} · ${String(record.url)}`,
  },
  {
    key: "education",
    endpoint: "education",
    title: "Education",
    description: "Keep degrees, coursework, and academic achievements in one place.",
    fields: [
      { name: "institution", label: "Institution", required: true },
      { name: "degree", label: "Degree", required: true },
      { name: "field_of_study", label: "Field of study" },
      { name: "start_date", label: "Start date", type: "date" },
      { name: "end_date", label: "End date", type: "date" },
      { name: "is_current", label: "Currently studying", type: "checkbox" },
      { name: "grade", label: "Grade / GPA" },
      { name: "coursework", label: "Coursework", type: "textarea" },
      { name: "achievements", label: "Achievements", type: "textarea" },
      { name: "description", label: "Description", type: "textarea" },
    ],
    summary: (record) => `${String(record.degree)} · ${String(record.institution)}`,
  },
  {
    key: "skills",
    endpoint: "skills",
    title: "Skills",
    description: "Record the skills you stand behind and how recently you used them.",
    fields: [
      { name: "name", label: "Skill", required: true },
      { name: "category", label: "Category", required: true, placeholder: "Technical" },
      { name: "proficiency", label: "Proficiency", type: "select", required: true, options: ["beginner", "intermediate", "advanced", "expert"].map((value) => ({ value, label: value[0].toUpperCase() + value.slice(1) })) },
      { name: "experience_months", label: "Experience (months)", type: "number" },
      { name: "last_used", label: "Last used", type: "date" },
    ],
    summary: (record) => `${String(record.name)} · ${String(record.proficiency)}`,
  },
  {
    key: "experience",
    endpoint: "experience",
    title: "Experience",
    description: "Capture roles and outcomes exactly as you want them represented.",
    fields: [
      { name: "company", label: "Company", required: true },
      { name: "title", label: "Title", required: true },
      { name: "employment_type", label: "Employment type", type: "select", required: true, options: ["full_time", "part_time", "internship", "contract", "temporary", "freelance"].map((value) => ({ value, label: value.replace("_", " ") })) },
      { name: "location", label: "Location" },
      { name: "start_date", label: "Start date", type: "date", required: true },
      { name: "end_date", label: "End date", type: "date" },
      { name: "is_current", label: "Currently working here", type: "checkbox" },
      { name: "description", label: "Description", type: "textarea" },
      { name: "achievements", label: "Achievements", type: "textarea" },
      { name: "technology_notes", label: "Technologies / related skills", type: "textarea" },
    ],
    summary: (record) => `${String(record.title)} · ${String(record.company)}`,
  },
  {
    key: "projects",
    endpoint: "projects",
    title: "Projects",
    description: "Show the projects and results that belong in your professional story.",
    fields: [
      { name: "name", label: "Project name", required: true },
      { name: "role", label: "Role" },
      { name: "github_url", label: "GitHub URL", type: "url" },
      { name: "live_url", label: "Live URL", type: "url" },
      { name: "start_date", label: "Start date", type: "date" },
      { name: "end_date", label: "End date", type: "date" },
      { name: "is_current", label: "Currently active", type: "checkbox" },
      { name: "description", label: "Description", type: "textarea" },
      { name: "problem_solved", label: "Problem solved", type: "textarea" },
      { name: "technology_notes", label: "Technologies", type: "textarea" },
      { name: "features", label: "Features", type: "textarea" },
      { name: "team_or_individual", label: "Team or individual", type: "select", options: [{ value: "individual", label: "Individual" }, { value: "team", label: "Team" }] },
      { name: "results", label: "Results", type: "textarea" },
    ],
    summary: (record) => String(record.name),
  },
  {
    key: "certifications",
    endpoint: "certifications",
    title: "Certifications",
    description: "Keep credentials and their evidence current.",
    fields: [
      { name: "name", label: "Certification", required: true },
      { name: "issuer", label: "Issuer", required: true },
      { name: "issue_date", label: "Issue date", type: "date" },
      { name: "expiry_date", label: "Expiry date", type: "date" },
      { name: "credential_id", label: "Credential ID" },
      { name: "credential_url", label: "Credential URL", type: "url" },
      { name: "description", label: "Description", type: "textarea" },
    ],
    summary: (record) => `${String(record.name)} · ${String(record.issuer)}`,
  },
  {
    key: "courses",
    endpoint: "courses",
    title: "Courses & training",
    description: "Add focused learning that supports your current direction.",
    fields: [
      { name: "name", label: "Course", required: true },
      { name: "provider", label: "Provider", required: true },
      { name: "completion_date", label: "Completion date", type: "date" },
      { name: "credential_url", label: "Credential URL", type: "url" },
      { name: "description", label: "Description", type: "textarea" },
    ],
    summary: (record) => `${String(record.name)} · ${String(record.provider)}`,
  },
  {
    key: "achievements",
    endpoint: "achievements",
    title: "Achievements",
    description: "Record milestones without turning them into inflated statistics.",
    fields: [
      { name: "title", label: "Achievement", required: true },
      { name: "organization", label: "Organization" },
      { name: "achieved_on", label: "Date", type: "date" },
      { name: "description", label: "Description", type: "textarea" },
      { name: "evidence_url", label: "Evidence URL", type: "url" },
    ],
    summary: (record) => String(record.title),
  },
  {
    key: "languages",
    endpoint: "languages",
    title: "Languages",
    description: "Describe the languages you use and your actual proficiency.",
    fields: [
      { name: "language", label: "Language", required: true },
      { name: "proficiency", label: "Proficiency", type: "select", required: true, options: ["basic", "conversational", "professional", "fluent", "native"].map((value) => ({ value, label: value[0].toUpperCase() + value.slice(1) })) },
    ],
    summary: (record) => `${String(record.language)} · ${String(record.proficiency)}`,
  },
  {
    key: "open_source_contributions",
    endpoint: "open-source",
    title: "Open-source contributions",
    description: "Keep a source-linked record of public contributions.",
    fields: [
      { name: "repository", label: "Repository", required: true, placeholder: "owner/project" },
      { name: "contribution", label: "Contribution", required: true },
      { name: "url", label: "URL", type: "url", required: true },
      { name: "technology_notes", label: "Technologies", type: "textarea" },
      { name: "start_date", label: "Start date", type: "date" },
      { name: "end_date", label: "End date", type: "date" },
      { name: "description", label: "Description", type: "textarea" },
    ],
    summary: (record) => `${String(record.repository)} · ${String(record.contribution)}`,
  },
];

export function PassportPage() {
  const [passport, setPassport] = useState<Passport | null>(null);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadPassport = useCallback(async () => {
    setLoading(true);
    setPageError(null);
    try {
      setPassport(await apiRequest<Passport>("/passport"));
    } catch (error) {
      setPageError(error instanceof ApiError ? error.message : "We could not load your Career Passport.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void loadPassport(); }, [loadPassport]);

  const saved = useCallback((message: string) => {
    setNotice(message);
    void loadPassport();
    window.setTimeout(() => setNotice(null), 3500);
  }, [loadPassport]);

  if (loading) {
  return <PageFrame><Card className="p-8"><div className="h-5 w-40 animate-pulse rounded bg-slate-100" /><div className="mt-4 h-3 w-full animate-pulse rounded bg-slate-100" /><div className="mt-2 h-3 w-3/4 animate-pulse rounded bg-slate-100" /></Card></PageFrame>;
  }

  if (pageError) {
    return <PageFrame><Card className="p-8"><Message tone="error">{pageError}</Message><div className="mt-5 flex gap-3"><Button onClick={() => void loadPassport()}>Try again</Button><Button asChild variant="secondary"><Link href="/login">Sign in</Link></Button></div></Card></PageFrame>;
  }

  if (!passport) return null;

  return (
    <PageFrame>
      <header className="flex flex-col gap-5 border-b border-line pb-7 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <Link className="inline-flex items-center gap-2 text-sm font-medium text-muted hover:text-ink" href="/"><ArrowLeft className="size-4" aria-hidden="true" /> Home</Link>
          <p className="mt-7 text-sm font-semibold uppercase tracking-[0.16em] text-brand">Career Passport</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-[-0.03em] text-ink sm:text-4xl">Your career, at your own pace.</h1>
          <p className="mt-3 max-w-2xl leading-7 text-muted">This profile is optional. Add only what helps your next move. You don’t need to complete every section to check or import a resume.</p>
          <Link className="mt-4 inline-flex text-sm font-semibold text-brand hover:text-indigo-700" href="/resumes">Open your resumes <span aria-hidden="true">→</span></Link>
        </div>
        <div className="min-w-56 rounded-xl border border-line bg-white p-4 shadow-panel" aria-label={`Passport completeness ${passport.completeness} percent`}>
          <div className="flex items-center justify-between text-sm"><span className="font-medium text-ink">Passport completeness</span><span className="font-semibold text-brand">{passport.completeness}%</span></div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-brand transition-all" style={{ width: `${passport.completeness}%` }} /></div>
          <p className="mt-2 text-xs text-muted">Optional section coverage, not a resume quality score.</p>
        </div>
      </header>

      <div className="mt-6 flex flex-wrap items-center justify-between gap-4 rounded-xl border border-emerald-200 bg-emerald-50 p-5"><div><h2 className="font-semibold text-emerald-950">Already have a resume? Skip the forms.</h2><p className="mt-1 text-sm leading-6 text-emerald-800">Upload it, check what’s working, and save an editable draft.</p></div><Button asChild><Link href="/review">Start with my resume →</Link></Button></div>

      {notice && <div className="mt-6"><Message tone="success"><Check className="size-4" aria-hidden="true" />{notice}</Message></div>}

      <div className="mt-8 space-y-6">
        <ProfileSection profile={passport.profile} onSaved={saved} />
        <PreferencesSection preferences={passport.career_preferences} onSaved={saved} />
        {collectionDefinitions.map((definition) => <CollectionSection key={definition.key} definition={definition} records={passport[definition.key]} onSaved={saved} />)}
      </div>
    </PageFrame>
  );
}

function PageFrame({ children }: { children: ReactNode }) {
  return <main className="min-h-screen bg-slate-50 px-5 py-6 sm:px-8 sm:py-10 lg:px-12"><div className="mx-auto max-w-6xl">{children}</div></main>;
}

function Message({ children, tone }: { children: ReactNode; tone: "error" | "success" }) {
  return <div className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm ${tone === "error" ? "border-rose-200 bg-rose-50 text-rose-800" : "border-emerald-200 bg-emerald-50 text-emerald-800"}`} role="status">{tone === "error" && <CircleAlert className="size-4 shrink-0" aria-hidden="true" />}{children}</div>;
}

function FormLabel({ label, required, children }: { label: string; required?: boolean; children: ReactNode }) {
  return <label className="block text-sm font-medium text-ink"><span className="mb-1.5 block">{label}{required && <span className="ml-1 text-brand" aria-hidden="true">*</span>}</span>{children}</label>;
}

function ProfileSection({ profile, onSaved }: { profile: Profile | null; onSaved: (message: string) => void }) {
  const [form, setForm] = useState({ full_name: profile?.full_name ?? "", headline: profile?.headline ?? "", bio: profile?.bio ?? "", location: profile?.location ?? "", linkedin_url: profile?.linkedin_url ?? "", github_url: profile?.github_url ?? "", portfolio_url: profile?.portfolio_url ?? "", profile_photo_key: profile?.profile_photo_key ?? "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const update = (name: keyof typeof form, value: string) => setForm((current) => ({ ...current, [name]: value }));
  const save = async () => {
    setBusy(true); setError(null);
    try { await apiRequest<Profile>("/passport/profile", { method: "PUT", body: JSON.stringify({ ...form, other_links: profile?.other_links ?? [] }) }); onSaved("Personal information saved."); }
    catch (caught) { setError(caught instanceof ApiError ? caught.message : "Could not save personal information."); }
    finally { setBusy(false); }
  };
  return <Card className="p-6 sm:p-8"><SectionHeading eyebrow="01" title="Personal information" description="The details that identify you and frame the rest of your Passport." /><div className="mt-6 grid gap-5 sm:grid-cols-2"><FormLabel label="Full name" required><Input value={form.full_name} onChange={(event) => update("full_name", event.target.value)} /></FormLabel><FormLabel label="Location"><Input value={form.location} onChange={(event) => update("location", event.target.value)} placeholder="City, country or timezone" /></FormLabel><FormLabel label="Headline"><Input value={form.headline} onChange={(event) => update("headline", event.target.value)} placeholder="What do you do best?" /></FormLabel><FormLabel label="Profile image reference"><Input value={form.profile_photo_key} onChange={(event) => update("profile_photo_key", event.target.value)} placeholder="Optional storage reference" /></FormLabel><FormLabel label="Bio"><textarea className="min-h-32 w-full rounded-lg border border-line bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-2 focus:ring-indigo-100" value={form.bio} onChange={(event) => update("bio", event.target.value)} /></FormLabel><div className="grid gap-4"><FormLabel label="LinkedIn URL"><Input type="url" value={form.linkedin_url} onChange={(event) => update("linkedin_url", event.target.value)} placeholder="https://linkedin.com/in/..." /></FormLabel><FormLabel label="GitHub URL"><Input type="url" value={form.github_url} onChange={(event) => update("github_url", event.target.value)} placeholder="https://github.com/..." /></FormLabel><FormLabel label="Portfolio URL"><Input type="url" value={form.portfolio_url} onChange={(event) => update("portfolio_url", event.target.value)} placeholder="https://..." /></FormLabel></div></div><div className="mt-5 flex flex-wrap items-center justify-between gap-3"><p className="text-xs text-muted">Account: {profile?.email ?? "A verified account"}</p><div className="flex items-center gap-3">{error && <span className="text-sm text-rose-700">{error}</span>}<Button onClick={() => void save()} disabled={busy}><Save className="size-4" aria-hidden="true" />{busy ? "Saving…" : "Save personal information"}</Button></div></div></Card>;
}

function PreferencesSection({ preferences, onSaved }: { preferences: Preferences | null; onSaved: (message: string) => void }) {
  const [form, setForm] = useState({ desired_job_titles: listFields(preferences?.desired_job_titles), industries: listFields(preferences?.industries), preferred_locations: listFields(preferences?.preferred_locations), work_arrangements: listFields(preferences?.work_arrangements), employment_types: listFields(preferences?.employment_types), expected_salary_min: String(preferences?.expected_salary_min ?? ""), expected_salary_max: String(preferences?.expected_salary_max ?? ""), salary_currency: preferences?.salary_currency ?? "", willing_to_relocate: preferences?.willing_to_relocate ?? false, preferred_company_sizes: listFields(preferences?.preferred_company_sizes), company_preferences: preferences?.company_preferences ?? "", exclusions: listFields(preferences?.exclusions) });
  const [busy, setBusy] = useState(false); const [error, setError] = useState<string | null>(null);
  const text = (name: Exclude<keyof typeof form, "willing_to_relocate">, value: string) => setForm((current) => ({ ...current, [name]: value }));
  const save = async () => { setBusy(true); setError(null); try { await apiRequest("/passport/preferences", { method: "PUT", body: JSON.stringify({ ...form, desired_job_titles: parseList(form.desired_job_titles), industries: parseList(form.industries), preferred_locations: parseList(form.preferred_locations), work_arrangements: parseList(form.work_arrangements), employment_types: parseList(form.employment_types), preferred_company_sizes: parseList(form.preferred_company_sizes), exclusions: parseList(form.exclusions), expected_salary_min: form.expected_salary_min || null, expected_salary_max: form.expected_salary_max || null, salary_currency: form.salary_currency || null }) }); onSaved("Career preferences saved."); } catch (caught) { setError(caught instanceof ApiError ? caught.message : "Could not save career preferences."); } finally { setBusy(false); } };
  return <Card className="p-6 sm:p-8"><SectionHeading eyebrow="02" title="Career preferences" description="Capture the direction you are choosing today; these preferences remain editable." /><div className="mt-6 grid gap-5 sm:grid-cols-2"><FormLabel label="Desired job titles"><Input value={form.desired_job_titles} onChange={(event) => text("desired_job_titles", event.target.value)} placeholder="Product designer, UX researcher" /></FormLabel><FormLabel label="Industries"><Input value={form.industries} onChange={(event) => text("industries", event.target.value)} placeholder="Comma-separated" /></FormLabel><FormLabel label="Preferred locations"><Input value={form.preferred_locations} onChange={(event) => text("preferred_locations", event.target.value)} /></FormLabel><FormLabel label="Work arrangements"><Input value={form.work_arrangements} onChange={(event) => text("work_arrangements", event.target.value)} placeholder="remote, hybrid or on_site" /></FormLabel><FormLabel label="Employment types"><Input value={form.employment_types} onChange={(event) => text("employment_types", event.target.value)} placeholder="full_time, contract" /></FormLabel><FormLabel label="Company sizes"><Input value={form.preferred_company_sizes} onChange={(event) => text("preferred_company_sizes", event.target.value)} /></FormLabel><FormLabel label="Minimum salary"><Input type="number" min="0" step="0.01" value={form.expected_salary_min} onChange={(event) => text("expected_salary_min", event.target.value)} /></FormLabel><FormLabel label="Maximum salary"><Input type="number" min="0" step="0.01" value={form.expected_salary_max} onChange={(event) => text("expected_salary_max", event.target.value)} /></FormLabel><FormLabel label="Currency"><Input maxLength={3} value={form.salary_currency} onChange={(event) => text("salary_currency", event.target.value.toUpperCase())} placeholder="USD" /></FormLabel><label className="flex items-center gap-3 pt-7 text-sm font-medium text-ink"><input className="size-4 accent-brand" type="checkbox" checked={form.willing_to_relocate} onChange={(event) => setForm((current) => ({ ...current, willing_to_relocate: event.target.checked }))} />Willing to relocate</label><FormLabel label="Company preferences"><textarea className="min-h-24 w-full rounded-lg border border-line bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-2 focus:ring-indigo-100" value={form.company_preferences} onChange={(event) => text("company_preferences", event.target.value)} /></FormLabel><FormLabel label="Exclusions"><Input value={form.exclusions} onChange={(event) => text("exclusions", event.target.value)} placeholder="Comma-separated" /></FormLabel></div><div className="mt-5 flex justify-end gap-3">{error && <span className="self-center text-sm text-rose-700">{error}</span>}<Button onClick={() => void save()} disabled={busy}><Save className="size-4" aria-hidden="true" />{busy ? "Saving…" : "Save preferences"}</Button></div></Card>;
}

function SectionHeading({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) { return <div><p className="text-xs font-semibold uppercase tracking-[0.16em] text-brand">{eyebrow}</p><h2 className="mt-2 text-xl font-semibold text-ink">{title}</h2><p className="mt-1 text-sm leading-6 text-muted">{description}</p></div>; }

function CollectionSection({ definition, records, onSaved }: { definition: (typeof collectionDefinitions)[number]; records: PassportRecord[]; onSaved: (message: string) => void }) {
  const [open, setOpen] = useState(false); const [editing, setEditing] = useState<PassportRecord | null>(null);
  const [draft, setDraft] = useState<Record<string, FormValue>>({}); const [busy, setBusy] = useState(false); const [error, setError] = useState<string | null>(null);
  const begin = (record?: PassportRecord) => { setEditing(record ?? null); setDraft(Object.fromEntries(definition.fields.map((field) => [field.name, field.type === "checkbox" ? Boolean(record?.[field.name]) : record?.[field.name] == null ? "" : String(record[field.name])] ))); setError(null); setOpen(true); };
  const close = () => { setOpen(false); setEditing(null); setDraft({}); setError(null); };
  const save = async () => { setBusy(true); setError(null); const payload: Record<string, unknown> = {}; definition.fields.forEach((field) => { const value = draft[field.name]; if (field.type === "checkbox") payload[field.name] = Boolean(value); else if (typeof value === "string" && value.trim() !== "") payload[field.name] = field.type === "number" ? Number(value) : value; }); try { await apiRequest(`${"/passport/"}${definition.endpoint}${editing ? `/${editing.id}` : ""}`, { method: editing ? "PATCH" : "POST", body: JSON.stringify(payload) }); close(); onSaved(`${definition.title} ${editing ? "updated" : "added"}.`); } catch (caught) { setError(caught instanceof ApiError ? caught.message : `Could not save ${definition.title.toLowerCase()}.`); } finally { setBusy(false); } };
  const remove = async (record: PassportRecord) => { if (!window.confirm(`Delete this ${definition.title.toLowerCase().replace("&", "and")} entry? This cannot be undone.`)) return; setError(null); try { await apiRequest(`/passport/${definition.endpoint}/${record.id}`, { method: "DELETE" }); onSaved(`${definition.title} entry deleted.`); } catch (caught) { setError(caught instanceof ApiError ? caught.message : "Could not delete this entry."); } };
  return <Card className="p-6 sm:p-8"><div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between"><div><p className="text-xs font-semibold uppercase tracking-[0.16em] text-brand">{definition.title}</p><h2 className="mt-2 text-xl font-semibold text-ink">{records.length ? `${records.length} ${records.length === 1 ? "entry" : "entries"}` : "Nothing added yet"}</h2><p className="mt-1 text-sm leading-6 text-muted">{definition.description}</p></div><Button onClick={() => begin()}><Plus className="size-4" aria-hidden="true" />Add entry</Button></div>{error && <div className="mt-4"><Message tone="error">{error}</Message></div>}{open && <div className="mt-6 rounded-xl border border-indigo-100 bg-indigo-50/40 p-5"><div className="flex items-center justify-between gap-4"><h3 className="font-semibold text-ink">{editing ? "Edit entry" : "Add entry"}</h3><button className="rounded p-1 text-muted hover:bg-white hover:text-ink" onClick={close} aria-label="Close form"><X className="size-4" /></button></div><div className="mt-5 grid gap-4 sm:grid-cols-2">{definition.fields.map((field) => <Field key={field.name} spec={field} value={draft[field.name] ?? (field.type === "checkbox" ? false : "")} onChange={(value) => setDraft((current) => ({ ...current, [field.name]: value }))} />)}</div><div className="mt-5 flex justify-end gap-3"><Button variant="secondary" onClick={close}>Cancel</Button><Button onClick={() => void save()} disabled={busy}><Save className="size-4" aria-hidden="true" />{busy ? "Saving…" : "Save entry"}</Button></div></div>}{records.length ? <div className="mt-6 grid gap-3 md:grid-cols-2">{records.map((record) => <div className="rounded-xl border border-line bg-slate-50 p-4" key={record.id}><div className="flex items-start justify-between gap-4"><div><p className="font-medium text-ink">{definition.summary(record)}</p><p className="mt-1 text-xs text-muted">Updated {formatDate(record.updated_at)}</p></div><ChevronDown className="mt-1 size-4 text-muted" aria-hidden="true" /></div><div className="mt-4 flex gap-2"><Button variant="secondary" className="h-9 px-3" onClick={() => begin(record)}>Edit</Button><Button variant="ghost" className="h-9 px-3 text-rose-700 hover:bg-rose-50 hover:text-rose-800" onClick={() => void remove(record)}><Trash2 className="size-4" aria-hidden="true" />Delete</Button></div></div>)}</div> : <div className="mt-6 rounded-lg border border-dashed border-line px-4 py-7 text-center text-sm text-muted">Add your first entry when you are ready. We never fill this section with invented information.</div>}</Card>;
}

function Field({ spec, value, onChange }: { spec: FieldSpec; value: FormValue; onChange: (value: FormValue) => void }) {
  if (spec.type === "checkbox") return <label className="flex items-center gap-3 pt-7 text-sm font-medium text-ink"><input className="size-4 accent-brand" type="checkbox" checked={Boolean(value)} onChange={(event) => onChange(event.target.checked)} />{spec.label}</label>;
  if (spec.type === "textarea") return <FormLabel label={spec.label} required={spec.required}><textarea className="min-h-24 w-full rounded-lg border border-line bg-white px-3 py-2 text-sm text-ink outline-none focus:border-brand focus:ring-2 focus:ring-indigo-100" required={spec.required} value={String(value)} onChange={(event) => onChange(event.target.value)} /></FormLabel>;
  if (spec.type === "select") return <FormLabel label={spec.label} required={spec.required}><select className="h-11 w-full rounded-lg border border-line bg-white px-3 text-sm text-ink outline-none focus:border-brand focus:ring-2 focus:ring-indigo-100" required={spec.required} value={String(value)} onChange={(event) => onChange(event.target.value)}><option value="">Select…</option>{spec.options?.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></FormLabel>;
  return <FormLabel label={spec.label} required={spec.required}><Input type={spec.type ?? "text"} required={spec.required} placeholder={spec.placeholder} value={String(value)} onChange={(event) => onChange(event.target.value)} /></FormLabel>;
}

function formatDate(value: unknown) { if (!value) return "not set"; const date = new Date(String(value)); return Number.isNaN(date.valueOf()) ? String(value) : new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(date); }
