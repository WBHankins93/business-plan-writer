import "./globals.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "Lender-ready business plans | Business Plan Writer",
  description: "Guided business plans for local owners preparing for an SBA or bank-loan conversation, with automated financial credibility checks and DOCX/PDF delivery.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
