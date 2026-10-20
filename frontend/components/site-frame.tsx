"use client";

import { usePathname } from "next/navigation";
import { SiteHeader } from "@/components/site-header";

export function SiteFrame({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  if (path === "/" || path === "/review") return children;
  const auth = ["/login", "/signup", "/signin", "/verify-email", "/forgot-password", "/reset-password"].includes(path);
  return <div className="application-shell">{!auth && <SiteHeader />}<div id="main-content">{children}</div></div>;
}
