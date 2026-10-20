import type { Metadata } from "next";
import { Plus_Jakarta_Sans } from "next/font/google";

import "./globals.css";
import { SiteFrame } from "@/components/site-frame";

const inter = Plus_Jakarta_Sans({ subsets: ["latin"], display: "swap" });

export const metadata: Metadata = {
  title: "CareerPilot",
  description: "Upload your resume, get evidence-based feedback, and build a stronger next draft. No lengthy forms. No signup to check.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={inter.className}><a href="#main-content" className="skip-link">Skip to content</a><SiteFrame>{children}</SiteFrame></body>
    </html>
  );
}
