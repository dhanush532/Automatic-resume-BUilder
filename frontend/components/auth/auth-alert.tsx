export function AuthAlert({ children, tone = "error" }: Readonly<{ children: React.ReactNode; tone?: "error" | "success" | "info" }>) {
  const tones = {
    error: "border-red-200 bg-red-50 text-red-800",
    success: "border-emerald-200 bg-emerald-50 text-emerald-800",
    info: "border-indigo-200 bg-indigo-50 text-indigo-900",
  };
  return <p className={`rounded-lg border px-3 py-2.5 text-sm leading-5 ${tones[tone]}`} role={tone === "error" ? "alert" : "status"}>{children}</p>;
}
