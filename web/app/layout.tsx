import "./globals.css";
import type { ReactNode } from "react";
import { DM_Sans, Newsreader } from "next/font/google";

const bodyFont = DM_Sans({
  subsets: ["latin"],
  variable: "--font-body",
  display: "swap",
});

const displayFont = Newsreader({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});

export const metadata = {
  title: "Funding-focused business plans | Business Plan Writer",
  description: "Human-reviewed business plans for operating local-service-business owners preparing for SBA-backed or conventional expansion financing.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className={`${bodyFont.variable} ${displayFont.variable}`}>{children}</body>
    </html>
  );
}
