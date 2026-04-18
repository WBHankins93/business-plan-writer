import "./globals.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "Business Plan Writer",
  description: "Web intake and draft review foundation",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

