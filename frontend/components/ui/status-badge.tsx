import { cn } from "@/lib/cn";

type StatusBadgeProps = {
  children: React.ReactNode;
  tone?: "neutral" | "warning" | "success";
};

export function StatusBadge({ children, tone = "neutral" }: StatusBadgeProps) {
  const tones = {
    neutral: "border-slate-200 bg-slate-50 text-slate-600",
    warning: "border-amber-200 bg-amber-50 text-amber-800",
    success: "border-emerald-200 bg-emerald-50 text-emerald-800",
  };

  return <span className={cn("inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium", tones[tone])}>{children}</span>;
}
