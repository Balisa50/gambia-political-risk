import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Gambia Political Risk Index",
  description:
    "Weekly Political Risk Index for The Gambia, derived from sentiment + topic analysis of Gambian news media.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-background text-white antialiased">{children}</body>
    </html>
  );
}
