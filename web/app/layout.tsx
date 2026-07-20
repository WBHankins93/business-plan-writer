import "./globals.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "Funding-focused business plans | Business Plan Writer",
  description: "Human-reviewed business plans for operating local-service-business owners preparing for SBA-backed or conventional expansion financing.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
